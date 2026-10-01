from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.adapters.passthrough_csv import write_passthrough_csv
from tint_sis.adapters.productos import leer_tabla
from tint_sis.adapters.sheet_filter import FormatoExpertoError, filtrar_libro
from tint_sis.backups import carpeta_backups, respaldar_filtrados
from tint_sis.db import repository
from tint_sis.db.database import DEFAULT_DB_PATH, get_session
from tint_sis.expertos import (
    ENABLED_GRUPOS,
    EXPERTOS,
    FILTRADOS_DIRNAME,
    PRODUCTOS_NAME,
    SOFTWARES_DEFAULT,
    SoftwareDef,
)
from tint_sis.routing import fecha_experto, find_latest_expert, matching_files

ProgressCallback = Callable[[dict], None]

STAGING_DIRNAME = ".staging"


def _emit(cb: ProgressCallback | None, **event: object) -> None:
    if cb is not None:
        cb(event)


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# Advertencia.tipo de un experto que no se pudo usar (falta, viene en .xls, no se
# pudo leer, la tabla no tiene su columna): sus softwares no se generaron y la
# app lo notifica aparte al terminar el ciclo
TIPO_EXPERTO = "experto"


@dataclass
class Advertencia:
    """Algo que quedo afuera del ciclo o hay que revisar. `detalle`: la lista
    completa de lo que se nombra (p. ej. cada producto sin asignar con sus filas)."""

    texto: str
    detalle: list[str] = field(default_factory=list)
    tipo: str = ""

    def to_dict(self) -> dict:
        return {"texto": self.texto, "detalle": list(self.detalle), "tipo": self.tipo}


@dataclass
class GeneratedFile:
    """Un archivo de salida concreto (alimenta la vista Resultados sin re-parsear)."""

    grupo: str
    tipo: str  # ".csv" | ".xlsx" | ".xlsm"
    filas: int
    ruta: str
    software: str


@dataclass
class PipelineSummary:
    advertencias: list[Advertencia] = field(default_factory=list)
    archivos: list[GeneratedFile] = field(default_factory=list)

    @property
    def ingestion_warnings(self) -> list[str]:
        return [a.texto for a in self.advertencias]

    @property
    def expertos_omitidos(self) -> list[Advertencia]:
        """Advertencias de expertos que no se pudieron usar en el ciclo."""
        return [a for a in self.advertencias if a.tipo == TIPO_EXPERTO]

    def avisar(self, texto: str, detalle: Iterable[str] = (), tipo: str = "") -> None:
        self.advertencias.append(Advertencia(texto, list(detalle), tipo))


@dataclass(frozen=True)
class _Trabajo:
    experto: str
    archivo: Path
    softwares: tuple[SoftwareDef, ...]
    tiendas: tuple[str, ...]  # union de las tiendas de sus softwares, en orden


def _tiendas_de(software: SoftwareDef, habilitadas: set[str]) -> list[str]:
    return [t for t in software.tiendas if t in habilitadas]


def planificar(
    input_dir: Path,
    softwares: Iterable[SoftwareDef],
    expertos_globs: Mapping[str, str],
    habilitadas: set[str],
    expertos_habilitados: set[str] | None = None,
) -> tuple[list[_Trabajo], list[Advertencia]]:
    """Que experto se filtra para que softwares/tiendas, y advertencias por
    expertos faltantes (TIPO_EXPERTO: sus softwares se omiten, el resto se
    genera igual). Los expertos desactivados (`expertos_habilitados`) se
    saltean sin aviso."""
    por_experto: dict[str, list[SoftwareDef]] = {}
    for sw in softwares:
        if expertos_habilitados is not None and sw.experto not in expertos_habilitados:
            continue
        if _tiendas_de(sw, habilitadas):
            por_experto.setdefault(sw.experto, []).append(sw)

    trabajos: list[_Trabajo] = []
    avisos: list[Advertencia] = []
    for experto in EXPERTOS:
        sws = por_experto.get(experto)
        if not sws:
            continue
        glob = expertos_globs.get(experto, EXPERTOS[experto].default_glob)
        archivo = find_latest_expert(input_dir, glob)
        nombres = ", ".join(s.nombre for s in sws)
        if archivo is None:
            prefijo = glob.split("*", 1)[0]
            viejos = [p.name for p in matching_files(input_dir, f"{prefijo}*.xls")]
            if viejos:
                texto = (
                    f"{experto}: {viejos[0]} esta en formato .xls (tope de 65.535 filas, "
                    f"queda truncado) - guardarlo como .xlsx. Se omiten {nombres}"
                )
            else:
                texto = f"Falta {experto} ({glob}) en la carpeta de entrada: se omiten {nombres}"
            avisos.append(Advertencia(texto, tipo=TIPO_EXPERTO))
            continue
        tiendas: list[str] = []
        for sw in sws:
            for t in _tiendas_de(sw, habilitadas):
                if t not in tiendas:
                    tiendas.append(t)
        trabajos.append(_Trabajo(experto, archivo, tuple(sws), tuple(tiendas)))
    return trabajos, avisos


def _aviso_sin_asignar(archivo: Path, sin_asignar, productos_name: str) -> Advertencia:
    """Productos de un experto que no estan en la tabla: el texto dice cuantos y
    el detalle los nombra a todos, de mas a menos filas."""
    items = sin_asignar.most_common()
    return Advertencia(
        f"{archivo.name}: {_miles(sum(sin_asignar.values()))} filas de {len(items)} producto(s) que no estan en "
        f"{productos_name} no se entregaron a ninguna tienda (agregarlos en Homólogos)",
        [f"{k} ({_miles(v)} filas)" for k, v in items],
    )


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    enabled_grupos: set[str] | None = None,
    expertos_habilitados: set[str] | None = None,
    productos_name: str = PRODUCTOS_NAME,
    expertos_globs: Mapping[str, str] | None = None,
    softwares: Iterable[SoftwareDef] | None = None,
    filtrados_dirname: str = FILTRADOS_DIRNAME,
    backups_dir: Path | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineSummary:
    """Filtra cada archivo experto por tienda segun la tabla de productos y
    entrega a cada software sus archivos en
    <output_dir>/<filtrados_dirname>/<Software>/<tienda>_ready_<DD_MM_YYYY>.<ext>, con la
    fecha del experto que lo alimenta (routing.fecha_experto).

    Antes de generar, lo que dejo el ciclo anterior en esa carpeta se mueve a
    `backups_dir` (default <output_dir>/../backups)/<fecha del ultimo ciclo>/
    (backups.respaldar_filtrados). Si algo no se puede mover (abierto en Excel)
    se lanza RespaldoError sin generar nada.

    Cada experto se lee una sola vez (sheet_filter.filtrar_libro) y genera el
    libro filtrado de cada tienda que necesitan sus softwares; los softwares en
    Excel reciben ese libro (misma extension que el experto: .xlsx / .xlsm), los
    en CSV la conversion con write_passthrough_csv. Si falta un experto se
    avisa y se omiten solo sus softwares; `expertos_habilitados` (default:
    todos) deja afuera del ciclo los expertos desactivados.

    `on_progress`, si se pasa, recibe eventos {fase, item, indice, total, ...}
    (fases: 'inicio', 'experto_inicio', 'experto_progreso', 'experto_ok',
    'mensaje', 'fin'); `item` es el label del experto."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    habilitadas = set(enabled_grupos) if enabled_grupos is not None else set(ENABLED_GRUPOS)
    softwares = list(softwares) if softwares is not None else list(SOFTWARES_DEFAULT)
    globs = dict(expertos_globs or {})
    filtrados = output_dir / filtrados_dirname
    staging = filtrados / STAGING_DIRNAME

    summary = PipelineSummary()
    tabla_path = input_dir / productos_name
    if not tabla_path.exists():
        summary.avisar(f"Falta la tabla de productos ({productos_name}) en la carpeta de entrada: no se genero nada")
        _emit(on_progress, fase="inicio", total=0, mensaje="Filtro por productos")
        _emit(on_progress, fase="fin", mensaje="Ciclo terminado", generados=0)
        return summary

    tabla = leer_tabla(tabla_path)
    for aviso in tabla.advertencias:
        summary.avisar(aviso)
    trabajos, avisos = planificar(input_dir, softwares, globs, habilitadas, expertos_habilitados)
    summary.advertencias.extend(avisos)

    session = get_session(db_path)
    try:
        _emit(on_progress, fase="inicio", total=len(trabajos), mensaje="Filtro por productos")
        # solo si el ciclo va a generar algo: si no, lo del ciclo anterior queda donde esta
        if trabajos:
            respaldo = respaldar_filtrados(
                filtrados,
                Path(backups_dir) if backups_dir else carpeta_backups(output_dir),
                session,
                excluir=(STAGING_DIRNAME,),
            )
            if respaldo is not None:
                aviso = f"Archivos del ciclo anterior movidos a {respaldo}"
                print(aviso)
                _emit(on_progress, fase="mensaje", mensaje=aviso)
        batch = repository.create_batch(session, origen_dir=str(input_dir))

        for indice, trabajo in enumerate(trabajos, start=1):
            _procesar_experto(
                trabajo, indice, len(trabajos), tabla, tabla_path.name, staging, filtrados,
                session, batch, summary, on_progress,
            )

        # quedan con el ciclo para verlas despues en Resultados / Historial
        repository.record_warnings(session, batch, [a.to_dict() for a in summary.advertencias])
        session.commit()
    finally:
        session.close()
        shutil.rmtree(staging, ignore_errors=True)

    _emit(on_progress, fase="fin", mensaje="Ciclo terminado", generados=len(summary.archivos))
    return summary


def _procesar_experto(
    trabajo: _Trabajo,
    indice: int,
    total: int,
    tabla,
    productos_name: str,
    staging: Path,
    filtrados: Path,
    session,
    batch,
    summary: PipelineSummary,
    on_progress: ProgressCallback | None,
) -> None:
    experto, archivo = trabajo.experto, trabajo.archivo
    base = dict(item=experto, indice=indice, total=total)
    rutas = tabla.rutas.get(experto)
    if rutas is None:
        summary.avisar(
            f"{productos_name} no tiene la columna '{experto}': se omiten "
            + ", ".join(s.nombre for s in trabajo.softwares),
            tipo=TIPO_EXPERTO,
        )
        return
    faltan = [t for t in trabajo.tiendas if t not in tabla.tiendas]
    if faltan:
        summary.avisar(f"{productos_name} no tiene columna para {', '.join(faltan)}: esas tiendas salen vacias")

    ext = archivo.suffix.lower()
    destinos = {t: staging / experto / f"{t}{ext}" for t in trabajo.tiendas}
    print(f"Filtrando {archivo.name} ({experto})...")
    _emit(
        on_progress,
        fase="experto_inicio",
        archivo=archivo.name,
        mensaje=f"{experto}: filtrando {archivo.name} para {', '.join(trabajo.tiendas)}",
        **base,
    )
    fecha, del_nombre = fecha_experto(archivo)
    if not del_nombre:
        aviso = (
            f"{archivo.name} no trae fecha en el nombre (_DD_MM_AAAA): sus archivos salen "
            f"con la fecha de modificacion, {fecha}"
        )
        print(aviso)
        _emit(on_progress, fase="mensaje", mensaje=aviso)

    def relay(etapa: str) -> ProgressCallback:
        def cb(ev: dict) -> None:
            _emit(
                on_progress,
                fase="experto_progreso",
                etapa="guardar" if ev.get("guardando") else etapa,
                leidas=ev.get("leidas"),
                sub_total=ev.get("total"),
                **base,
            )

        return cb

    try:
        resultado = filtrar_libro(
            archivo,
            destinos,
            rutas,
            EXPERTOS[experto].key_headers,
            on_progress=relay("filtrar") if on_progress else None,
        )
    except (FormatoExpertoError, OSError, KeyError) as exc:
        summary.avisar(
            f"{archivo.name}: no se pudo filtrar ({exc}). Se omiten "
            + ", ".join(s.nombre for s in trabajo.softwares),
            tipo=TIPO_EXPERTO,
        )
        _emit(on_progress, fase="experto_ok", mensaje=f"{experto}: error, se omite", filas=0, **base)
        return

    if resultado.sin_asignar:
        summary.advertencias.append(_aviso_sin_asignar(archivo, resultado.sin_asignar, productos_name))
    for tienda, filas in resultado.filas_por_tienda.items():
        if filas == 0 and tienda in tabla.tiendas:
            summary.avisar(f"{archivo.name}: ningun producto marcado para {tienda} en {productos_name}")

    for sw in trabajo.softwares:
        carpeta = filtrados / sw.nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        for tienda in sw.tiendas:
            if tienda not in destinos:
                continue
            origen = destinos[tienda]
            if sw.formato == "csv":
                destino = carpeta / f"{tienda}_ready_{fecha}.csv"
                _emit(
                    on_progress,
                    fase="mensaje",
                    mensaje=f"{sw.nombre}: escribiendo {destino.name}...",
                )
                filas = write_passthrough_csv(
                    origen,
                    destino,
                    on_progress=relay("csv") if on_progress else None,
                    total_hint=resultado.filas_por_tienda[tienda],
                    sheet_name=resultado.hoja,
                )
            else:
                destino = carpeta / f"{tienda}_ready_{fecha}{ext}"
                shutil.copyfile(origen, destino)
                filas = resultado.filas_por_tienda[tienda]
            repository.record_generated_file(
                session, batch, tienda, f"{sw.nombre}_{destino.suffix.lstrip('.')}", str(destino)
            )
            summary.archivos.append(GeneratedFile(tienda, destino.suffix.lower(), filas, str(destino), sw.nombre))

    _emit(
        on_progress,
        fase="experto_ok",
        mensaje=f"{experto}: " + ", ".join(f"{t} {n:,}".replace(",", ".") for t, n in resultado.filas_por_tienda.items()),
        filas=resultado.filas_leidas,
        **base,
    )
