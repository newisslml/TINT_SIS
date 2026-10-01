"""Rutas HTTP que consume la UI, cableadas al motor real de `tint_sis`."""
from __future__ import annotations

import datetime
import fnmatch
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from tint_sis.adapters.productos import TablaCambiadaError, guardar_edicion, leer_para_editar
from tint_sis.adapters.sheet_filter import FormatoExpertoError, contar_claves
from tint_sis.backups import BACKUPS_DIRNAME, carpeta_backups, clave_ruta
from tint_sis.config import AppConfig, load_config, save_config
from tint_sis.db import repository
from tint_sis.db.database import get_session
from tint_sis.expertos import EXPERTOS
from tint_sis.preparar import DecisionNuevo, ultimo_resumen
from tint_sis.preview import preview_batch
from tint_sis.routing import EXPERT_MASTER_GLOB, find_latest_expert

from . import _avisos, _preparar, _runner

# Donde se guardan los archivos maestros que se arrastran a "Nuevo ciclo"
# (<data>/maestros, hermana de la carpeta de entrada): no van a la entrada, que
# solo tiene lo que usa el ciclo.
MAESTROS_DIRNAME = "maestros"
# Copias de homologos_TINT.xlsx que deja cada guardado desde la vista Homologos
RESPALDO_PRODUCTOS_DIRNAME = "productos"

router = APIRouter()

# Catalogo de productos de cada experto (nombre -> formulas) para la vista
# Homologos: leer un experto entero tarda ~10 s, asi que se cachea por
# archivo + fecha de modificacion (se invalida solo cuando cambia el experto).
_catalogo_cache: dict[str, tuple[Path, int, dict[str, int]]] = {}


def _cfg() -> AppConfig:
    return load_config()


FMT_FECHA_HISTORIAL = "%d/%m/%y %H:%M"  # DD/MM/YY (pedido del usuario 2026-09-28)


def _fmt_dt(dt, formato: str = "%Y-%m-%d %H:%M") -> str:
    """Formatea una fecha de la DB en hora local. `creado_en` / `generado_en` se
    guardan en UTC (y vuelven naive tras el round-trip por SQLite), así que se les
    asigna UTC y se convierte a la zona local del equipo antes de mostrar."""
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone().strftime(formato)


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _count_data_rows(path: Path) -> int:
    """Cuenta filas de datos (sin encabezado) de un .csv ya generado."""
    try:
        with open(path, "rb") as fh:
            total = sum(1 for _ in fh)
        return max(0, total - 1)
    except OSError:
        return 0


# Carpetas donde el flujo anterior (un solo experto xData) dejaba los archivos.
_CARPETAS_FLUJO_ANTERIOR = ("xData", "Tiendas filtradas")


def _salida_de_registro(reg, filtrados_dirname: str, vigente: bool = True) -> tuple[str, dict, int]:
    """(software, fila para la UI, filas contadas) de un archivo generado. El
    software es la carpeta del archivo (<salida>/Archivos filtrados/<Software>/ o
    <data>/backups/<fecha>/<Software>/); los ciclos anteriores a la salida por
    software quedaban sueltos en la carpeta de filtrados (xData/ y despues
    Tiendas filtradas/). Las filas solo se cuentan para los .csv (contar un .xlsx
    obliga a abrirlo). `vigente=False`: un ciclo posterior escribio en la misma
    ruta, asi que el archivo en disco ya no es el de este ciclo."""
    ruta = Path(reg.ruta)
    software = ruta.parent.name
    if software in (filtrados_dirname, *_CARPETAS_FLUJO_ANTERIOR):
        software = "Flujo anterior (xData)"
    existe = vigente and ruta.exists()
    tipo = ruta.suffix.lower() or (".csv" if reg.adaptador.endswith("csv") else ".xlsx")
    filas = _count_data_rows(ruta) if tipo == ".csv" and existe else 0
    salida = {
        "salida": ruta.name,
        "tienda": reg.linea_producto,
        "tipo": tipo,
        "filas": _fmt_int(filas) if filas else "-",
        "existe": existe,
        "ruta": str(ruta),
    }
    return software, salida, filas


def _last_batch_files(cfg: AppConfig):
    """(fecha, grupos_dict, n_archivos, filas_totales, advertencias) del ultimo
    batch en la DB, o None si no hay ninguno. `grupos` va por software;
    `advertencias` es None en los ciclos de antes de que se guardaran."""
    session = get_session(cfg.db_path)
    try:
        batch = repository.get_last_batch(session)
        if batch is None:
            return None
        registros = repository.files_for_batch(session, batch)
        grupos: dict[str, list[dict]] = {}
        filas_totales = 0
        for reg in registros:
            software, salida, filas = _salida_de_registro(reg, cfg.filtrados_dirname)
            filas_totales += filas
            grupos.setdefault(software, []).append(salida)
        return {
            "fecha": _fmt_dt(batch.creado_en),
            "grupos": grupos,
            "n_archivos": len(registros),
            "filas_totales": _fmt_int(filas_totales),
            "advertencias": repository.warnings_for_batch(session, batch),
        }
    finally:
        session.close()


def _n_advertencias(advertencias: list | None):
    """Cantidad para mostrar: "-" si el ciclo es de antes de que se guardaran."""
    return "-" if advertencias is None else len(advertencias)


# --------------------------------------------------------------------------- #
# rutas
# --------------------------------------------------------------------------- #
@router.get("/estado")
def get_estado() -> dict:
    cfg = _cfg()
    last = _last_batch_files(cfg)
    softwares = [s.nombre for s in cfg.softwares_activos()]
    return {
        "carpeta_trabajo": str(Path(cfg.input_dir).parent),
        "ultimo_ciclo": last["fecha"] if last else "sin ciclos",
        "software": ", ".join(softwares) or "-",
    }


@router.get("/inicio")
def get_inicio() -> dict:
    cfg = _cfg()
    last = _last_batch_files(cfg)
    prev = preview_batch(cfg)

    # rojo lo que impide ejecutar, naranjo lo que queda afuera
    alertas = [{"nivel": "error", "texto": b} for b in prev.bloqueantes] + [
        {"nivel": "advertencia", "texto": a} for a in prev.advertencias
    ]

    mem = _runner.last_summary()
    advertencias = (
        mem["resumen"]["advertencias"] if mem else (0 if last is None else _n_advertencias(last["advertencias"]))
    )

    return {
        "ultimo_ciclo": {
            "fecha": last["fecha"] if last else "-",
            "experto": " · ".join(e.archivo for e in prev.expertos if e.archivo)
            or "(sin expertos en la carpeta)",
            "archivos_generados": last["n_archivos"] if last else 0,
            "advertencias": advertencias,
        },
        "alertas": alertas,
    }


@router.get("/preview")
def get_preview() -> dict:
    return preview_batch(_cfg()).to_dict()


@router.get("/avisos")
def get_avisos(desde: int = -1) -> dict:
    """Avisos de fin de trabajo (preparacion, ciclo) posteriores al id `desde`;
    con -1 solo el ultimo id. La UI los consulta seguido desde cualquier vista."""
    return _avisos.desde(desde)


@router.post("/run")
def post_run() -> dict:
    cfg = _cfg()
    if _preparar.ocupado():
        raise HTTPException(status_code=409, detail="Se están preparando los expertos: esperar a que termine")
    prev = preview_batch(cfg)
    if not prev.puede_ejecutar:
        raise HTTPException(status_code=409, detail="; ".join(prev.bloqueantes) or "No se puede ejecutar")
    if not _runner.start(cfg):
        raise HTTPException(status_code=409, detail="Ya hay una corrida en curso")
    return _runner.snapshot()


@router.get("/run/current")
def get_run_current() -> dict:
    return _runner.snapshot()


@router.post("/run/cancel")
def post_run_cancel() -> dict:
    _runner.request_cancel()
    return _runner.snapshot()


@router.get("/resultados")
def get_resultados() -> dict:
    mem = _runner.last_summary()
    if mem is not None:
        return mem

    cfg = _cfg()
    last = _last_batch_files(cfg)
    if last is None:
        return {"resumen": {"archivos": 0, "filas_totales": "0", "advertencias": 0}, "grupos": [], "advertencias": []}
    return {
        "resumen": {
            "archivos": last["n_archivos"],
            "filas_totales": last["filas_totales"],
            "advertencias": _n_advertencias(last["advertencias"]),
        },
        "grupos": [{"titulo": software, "salidas": s} for software, s in last["grupos"].items()],
        "advertencias": last["advertencias"] or [],
        "fecha": last["fecha"],
    }


@router.get("/historial")
def get_historial() -> dict:
    """Lista los ciclos ejecutados (batches en la DB) con sus archivos generados,
    marcando cuáles siguen disponibles en disco para revisar el backup."""
    cfg = _cfg()
    session = get_session(cfg.db_path)
    try:
        ciclos = []
        # rutas ya tomadas por un ciclo mas nuevo: antes del respaldo en backups/
        # cada ciclo pisaba los archivos del anterior, que ya no estan en disco
        reclamadas: set[str] = set()
        for batch in repository.list_batches(session, limit=50):  # del mas nuevo al mas viejo
            registros = repository.files_for_batch(session, batch)
            grupos: dict[str, list[dict]] = {}
            filas_totales = 0
            disponibles = 0
            carpetas: list[Path] = []
            carpeta_viva = None
            for reg in registros:
                vigente = clave_ruta(reg.ruta) not in reclamadas
                software, salida, filas = _salida_de_registro(reg, cfg.filtrados_dirname, vigente)
                ruta = Path(reg.ruta)
                if salida["existe"]:
                    disponibles += 1
                    if carpeta_viva is None:
                        carpeta_viva = _carpeta_ciclo(ruta, cfg.filtrados_dirname)
                filas_totales += filas
                carpeta_reg = _carpeta_ciclo(ruta, cfg.filtrados_dirname)
                if carpeta_reg not in carpetas:
                    carpetas.append(carpeta_reg)
                grupos.setdefault(software, []).append(salida)
            reclamadas.update(clave_ruta(reg.ruta) for reg in registros)
            # carpeta local del backup: la del primer archivo que aún existe, o la
            # esperada (la del primer registro) si ninguno sigue en disco
            carpeta = carpeta_viva or (carpetas[0] if carpetas else None)
            advertencias = repository.warnings_for_batch(session, batch)
            ciclos.append(
                {
                    "id": batch.id,
                    "fecha": _fmt_dt(batch.creado_en, FMT_FECHA_HISTORIAL),
                    "origen": batch.origen_dir,
                    # None: ciclo de antes de que se guardaran las advertencias
                    "advertencias": advertencias,
                    "n_archivos": len(registros),
                    "n_disponibles": disponibles,
                    "filas_totales": _fmt_int(filas_totales),
                    "carpeta": str(carpeta) if carpeta else None,
                    # solo si le queda algun archivo propio: la carpeta de un ciclo
                    # pisado existe, pero tiene los archivos de otro ciclo
                    "carpeta_existe": bool(carpeta_viva and carpeta_viva.is_dir()),
                    "grupos": [{"titulo": software, "salidas": s} for software, s in grupos.items()],
                }
            )
        return {"ciclos": ciclos}
    finally:
        session.close()


def _carpeta_ciclo(ruta: Path, filtrados_dirname: str) -> Path:
    """Carpeta que agrupa todas las salidas de un ciclo: la de los filtrados
    (padre de las carpetas por software) o, ya respaldado, la de su fecha en
    backups/. Para registros viejos (antes de la salida por software) es la
    carpeta del propio archivo."""
    if ruta.parent.parent.name == filtrados_dirname:
        return ruta.parent.parent
    if ruta.parent.parent.parent.name == BACKUPS_DIRNAME:  # backups/<fecha>/<Software>/<archivo>
        return ruta.parent.parent
    return ruta.parent


def _reveal_roots(cfg: AppConfig) -> list[Path]:
    """Carpetas bajo las que se permite abrir algo desde la UI: la salida
    configurada, la de backups y la carpeta de trabajo."""
    roots = []
    for candidato in (Path(cfg.output_dir), carpeta_backups(cfg.output_dir), Path(cfg.input_dir).parent):
        try:
            resuelto = candidato.resolve()
        except OSError:
            continue
        if resuelto not in roots:
            roots.append(resuelto)
    return roots


@router.post("/reveal")
def post_reveal(payload: dict) -> dict:
    """Abre en el explorador un archivo generado por un ciclo, o la carpeta que lo
    contiene. Sólo se permiten rutas dentro de la carpeta de salida o de trabajo."""
    raw = (payload or {}).get("ruta", "")
    modo = (payload or {}).get("modo", "carpeta")
    if not raw:
        raise HTTPException(status_code=400, detail="Falta 'ruta'")

    cfg = _cfg()
    try:
        objetivo = Path(raw).resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Ruta inválida") from exc
    if not any(objetivo == r or r in objetivo.parents for r in _reveal_roots(cfg)):
        raise HTTPException(status_code=400, detail="Ruta fuera de la carpeta de trabajo")

    if objetivo.is_dir():
        destino = objetivo
    elif modo == "archivo" and objetivo.is_file():
        destino = objetivo
    else:
        destino = objetivo.parent
    if not destino.exists():
        raise HTTPException(status_code=404, detail=f"Ya no existe en disco: {destino}")
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(destino))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(destino)])
        else:
            subprocess.Popen(["xdg-open", str(destino)])
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir: {exc}") from exc
    return {"abierto": str(destino)}


@router.get("/config")
def get_config() -> dict:
    return _cfg().to_dict()


@router.put("/config")
def put_config(nuevo: dict) -> dict:
    actual = _cfg().to_dict()
    actual.update({k: v for k, v in nuevo.items() if k in actual})
    cfg = AppConfig.from_dict(actual)
    path = save_config(cfg)
    return {"guardado": True, "config": cfg.to_dict(), "archivo": str(path)}


@router.post("/input/open")
def post_input_open() -> dict:
    cfg = _cfg()
    carpeta = Path(cfg.input_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(carpeta))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir la carpeta: {exc}") from exc
    return {"abierto": str(carpeta)}


def es_archivo_de_entrada(cfg: AppConfig, nombre: str) -> bool:
    """True si `nombre` es un archivo que va tal cual a la carpeta de entrada
    (un Experto_1/2/3, tambien en .xls para que el preview avise; la tabla de
    productos; o los del flujo anterior). Cualquier otro Excel que se arrastra a
    "Nuevo ciclo" se toma como el archivo maestro de tintometria."""
    if nombre in (cfg.productos_name, cfg.homologos_master_name) or fnmatch.fnmatch(nombre, EXPERT_MASTER_GLOB):
        return True
    return any(fnmatch.fnmatch(nombre, glob.split("*", 1)[0] + "*") for glob in cfg.expertos.values())


@router.post("/input/upload")
async def post_input_upload(file: UploadFile) -> dict:
    """Dropzone de "Nuevo ciclo". Un experto o la tabla se copian a la carpeta de
    entrada (tipo "entrada"); cualquier otro archivo es el maestro de
    tintometria y arranca su analisis (tipo "maestro", ver /preparar/*)."""
    cfg = _cfg()
    nombre = Path(file.filename or "archivo.xlsx").name
    if not es_archivo_de_entrada(cfg, nombre):
        return {"tipo": "maestro", "preparar": _recibir_maestro(cfg, nombre, await file.read())}
    carpeta = Path(cfg.input_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre
    data = await file.read()
    destino.write_bytes(data)
    return {"tipo": "entrada", "guardado": nombre, "preview": preview_batch(cfg).to_dict()}


# --------------------------------------------------------------------------- #
# preparar experto (archivo maestro -> Experto 1/2/3 + tabla de productos)
# --------------------------------------------------------------------------- #
def _resumen_corto(guardado: dict | None) -> dict | None:
    """Lo que muestra la vista de la ultima preparacion guardada en disco."""
    if not guardado:
        return None
    analisis = guardado.get("analisis") or {}
    resultado = guardado.get("resultado") or {}
    return {
        "preparado_en": guardado.get("preparado_en"),
        "maestro": analisis.get("maestro"),
        "fecha": analisis.get("fecha"),
        "nuevos": [
            {"linea": n.get("linea"), "producto": n.get("producto"), "filas": n.get("filas")}
            for n in analisis.get("nuevos") or []
        ],
        "archivos": resultado.get("archivos") or [],
        "resumen_xlsx": resultado.get("resumen_xlsx"),
    }


@router.get("/preparar/estado")
def get_preparar_estado() -> dict:
    snap = _preparar.snapshot()
    snap["ultimo"] = _resumen_corto(ultimo_resumen(_cfg())) if snap["estado"] == "idle" else None
    return snap


def _recibir_maestro(cfg: AppConfig, nombre: str, data: bytes) -> dict:
    """Guarda el archivo maestro en <data>/maestros/ y lo analiza en segundo plano
    (la UI sigue el progreso con /preparar/estado)."""
    if _preparar.ocupado():
        raise HTTPException(status_code=409, detail="Ya hay un análisis o una preparación en curso")
    if _runner.is_running():
        raise HTTPException(status_code=409, detail="Hay un ciclo en curso: esperar a que termine")
    if Path(nombre).suffix.lower() not in (".xlsx", ".xlsm"):
        raise HTTPException(
            status_code=400, detail="El maestro tiene que ser .xlsx (el .xls corta en 65.535 filas)"
        )
    carpeta = Path(cfg.input_dir).parent / MAESTROS_DIRNAME
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre
    destino.write_bytes(data)
    if not _preparar.iniciar_analisis(cfg, destino):
        raise HTTPException(status_code=409, detail="Ya hay un análisis o una preparación en curso")
    return get_preparar_estado()


@router.post("/preparar/maestro")
async def post_preparar_maestro(file: UploadFile) -> dict:
    """Recibe siempre el archivo como maestro (sin mirar el nombre)."""
    return _recibir_maestro(_cfg(), Path(file.filename or "maestro.xlsx").name, await file.read())


@router.post("/preparar/confirmar")
def post_preparar_confirmar(payload: dict) -> dict:
    """Prepara los expertos con el analisis en memoria. `nuevos`: clave del
    producto nuevo -> {tiendas, nombre_e2, nombre_e3, linea}."""
    if _runner.is_running():
        raise HTTPException(status_code=409, detail="Hay un ciclo en curso: esperar a que termine")
    decisiones = {}
    for clave, d in ((payload or {}).get("nuevos") or {}).items():
        d = d or {}
        decisiones[str(clave)] = DecisionNuevo(
            tiendas=[str(t) for t in d.get("tiendas") or []],
            nombre_e2=str(d.get("nombre_e2") or "").strip(),
            nombre_e3=str(d.get("nombre_e3") or "").strip(),
            linea=(str(d["linea"]).strip() or None) if d.get("linea") else None,
        )
    motivo = _preparar.iniciar_preparacion(_cfg(), decisiones)
    if motivo:
        raise HTTPException(status_code=409, detail=motivo)
    return get_preparar_estado()


@router.post("/preparar/reiniciar")
def post_preparar_reiniciar() -> dict:
    _preparar.reiniciar()
    return get_preparar_estado()


# --------------------------------------------------------------------------- #
# homologos: la tabla de productos (homologos_TINT.xlsx)
# --------------------------------------------------------------------------- #
def _tabla_productos(cfg: AppConfig) -> Path:
    path = Path(cfg.input_dir) / cfg.productos_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No está {cfg.productos_name} en la carpeta de entrada")
    return path


@router.get("/productos")
def get_productos() -> dict:
    """La tabla de productos para editar: {archivo, tiendas, version, filas}."""
    cfg = _cfg()
    path = _tabla_productos(cfg)
    try:
        tabla = leer_para_editar(path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo leer {path.name}: {exc}") from exc
    return {"archivo": path.name, **tabla}


@router.put("/productos")
def put_productos(payload: dict) -> dict:
    """Guarda la tabla editada (todas las filas, en orden; las que no vienen se
    eliminan). Antes deja una copia en <data>/backups/productos/<fecha>/."""
    cfg = _cfg()
    path = _tabla_productos(cfg)
    if _preparar.ocupado() or _runner.is_running():
        raise HTTPException(status_code=409, detail="Hay una preparación o un ciclo en curso: esperar a que termine")
    ahora = datetime.datetime.now()
    try:
        respaldo = guardar_edicion(
            path,
            list((payload or {}).get("filas") or []),
            version=(payload or {}).get("version"),
            respaldo_dir=carpeta_backups(cfg.output_dir) / RESPALDO_PRODUCTOS_DIRNAME / ahora.strftime("%Y-%m-%d_%H-%M-%S"),
            nota_nuevas=f"Agregado en Homólogos {ahora.strftime('%d/%m/%Y')}",
        )
    except TablaCambiadaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=409, detail=f"{path.name} está abierto (por ejemplo en Excel): cerralo y volvé a guardar"
        ) from exc
    return {"guardado": True, "respaldo": str(respaldo), **get_productos()}


def _catalogo(label: str, path: Path) -> dict[str, int]:
    mtime = path.stat().st_mtime_ns
    cache = _catalogo_cache.get(label)
    if cache is not None and cache[0] == path and cache[1] == mtime:
        return cache[2]
    conteo = dict(contar_claves(path, EXPERTOS[label].key_headers))
    _catalogo_cache[label] = (path, mtime, conteo)
    return conteo


@router.get("/productos/catalogo")
def get_productos_catalogo() -> dict:
    """Productos que trae cada experto del ciclo (nombre -> formulas), para
    contar formulas por fila y mostrar los que faltan en la tabla. La primera
    vez lee los expertos (~30 s); despues sale de la cache."""
    cfg = _cfg()
    out = {}
    for label, definicion in EXPERTOS.items():
        path = find_latest_expert(Path(cfg.input_dir), cfg.expertos.get(label, definicion.default_glob))
        if path is None:
            out[label] = {"archivo": None, "productos": {}, "error": "no está en la carpeta de entrada"}
            continue
        try:
            out[label] = {"archivo": path.name, "productos": _catalogo(label, path), "error": None}
        except (FormatoExpertoError, OSError, KeyError) as exc:
            out[label] = {"archivo": path.name, "productos": {}, "error": str(exc)}
    return {"expertos": out}
