"""Previsualizacion de un ciclo (dry-run) — plan PLAN_APP_TINT_SIS.md §5.3.

Mira que hay en la carpeta de entrada y clasifica cada archivo Excel sin correr
el filtro. Alimenta la vista "Nuevo ciclo".
"""
from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tint_sis.config import AppConfig
from tint_sis.expertos import EXPERTOS
from tint_sis.routing import EXPERT_MASTER_GLOB, expert_master_sort_key, find_latest_expert


@dataclass
class PlannedFile:
    archivo: str
    software: str  # softwares destino ("Santint, Corob_Tint") | "-"
    flujo: str  # "Experto N" | "Tabla de productos" | "-"
    estado: str  # "ok" | "no-habilitado" | "desactivado" | "error"
    detalle: str


@dataclass
class ExpertoPreview:
    label: str
    archivo: str | None
    softwares: list[str]
    estado: str  # "ok" | "falta" | "desactivado"
    # por software: {nombre, tiendas (solo las habilitadas), formato} -> resumen antes de ejecutar
    detalle: list[dict] = field(default_factory=list)


@dataclass
class BatchPreview:
    productos_activo: str | None
    expertos: list[ExpertoPreview]
    tiendas_habilitadas: list[str]
    archivos: list[PlannedFile]
    puede_ejecutar: bool
    bloqueantes: list[str]
    advertencias: list[str]
    salida: str | None = None  # carpeta donde quedan las subcarpetas por software

    def to_dict(self) -> dict:
        return asdict(self)


def _es_excel(path: Path) -> bool:
    return path.suffix.lower() in (".xlsx", ".xlsm", ".xls") and not path.name.startswith("~$")


def preview_batch(config: AppConfig) -> BatchPreview:
    input_dir = Path(config.input_dir)
    habilitadas = set(config.enabled_grupos)
    tiendas = sorted(habilitadas)
    softwares = [s for s in config.software_defs() if any(t in habilitadas for t in s.tiendas)]
    softwares_de = {e: [s.nombre for s in softwares if s.experto == e] for e in EXPERTOS}
    detalle_de = {
        e: [
            {"nombre": s.nombre, "tiendas": [t for t in s.tiendas if t in habilitadas], "formato": s.formato}
            for s in softwares
            if s.experto == e
        ]
        for e in EXPERTOS
    }
    salida = str(Path(config.output_dir) / config.filtrados_dirname)

    if not input_dir.exists():
        return BatchPreview(
            None, [], tiendas, [], False, [f"La carpeta de entrada no existe: {input_dir}"], [], salida
        )

    productos_ok = (input_dir / config.productos_name).exists()
    habilitados = set(config.expertos_habilitados)
    ultimos: dict[str, Path | None] = {
        e: find_latest_expert(input_dir, config.expertos.get(e, d.default_glob)) for e, d in EXPERTOS.items()
    }
    # el experto que usa el ciclo: habilitado, con algun software activo y en la carpeta
    activos: dict[str, Path | None] = {
        e: ultimos[e] if e in habilitados and softwares_de[e] else None for e in EXPERTOS
    }

    archivos: list[PlannedFile] = []
    # Orden por fecha, mas nuevo arriba: los expertos con fecha DD_MM_YYYY en el
    # nombre quedan primero (el que va a usar el ciclo arriba); los archivos sin
    # fecha van despues, ordenados por mtime descendente.
    for path in sorted(
        (p for p in input_dir.iterdir() if p.is_file() and _es_excel(p)),
        key=expert_master_sort_key,
        reverse=True,
    ):
        archivos.append(_clasificar(path, config, activos, softwares_de, habilitados))

    bloqueantes: list[str] = []
    advertencias: list[str] = []
    if not productos_ok:
        bloqueantes.append(
            f"Falta la tabla de productos ({config.productos_name}) en la carpeta de entrada. "
            "Se arma una sola vez con: python -m tint_sis.cli productos-init"
        )
    expertos: list[ExpertoPreview] = []
    for e in EXPERTOS:
        if not softwares_de[e]:
            continue
        if e not in habilitados:
            archivo = ultimos[e]
            expertos.append(
                ExpertoPreview(e, archivo.name if archivo else None, softwares_de[e], "desactivado", detalle_de[e])
            )
            continue
        archivo = activos[e]
        expertos.append(
            ExpertoPreview(
                e, archivo.name if archivo else None, softwares_de[e], "ok" if archivo else "falta", detalle_de[e]
            )
        )
    en_uso = [x for x in expertos if x.estado != "desactivado"]
    if not en_uso:
        bloqueantes.append("No hay ningun experto habilitado: activa al menos uno en Configuracion")
    elif not any(x.archivo for x in en_uso):
        bloqueantes.append("No hay ningun archivo experto habilitado (Experto_1 / Experto_2 / Experto_3) en la carpeta de entrada")
    else:
        for x in en_uso:
            if x.archivo is None:
                advertencias.append(f"Falta {x.label}: se omiten {', '.join(x.softwares)}")

    return BatchPreview(
        productos_activo=config.productos_name if productos_ok else None,
        expertos=expertos,
        tiendas_habilitadas=tiendas,
        archivos=archivos,
        puede_ejecutar=not bloqueantes,
        bloqueantes=bloqueantes,
        advertencias=advertencias,
        salida=salida,
    )


def _clasificar(
    path: Path,
    config: AppConfig,
    activos: dict[str, Path | None],
    softwares_de: dict[str, list[str]],
    habilitados: set[str],
) -> PlannedFile:
    name = path.name
    if name == config.productos_name:
        return PlannedFile(name, "-", "Tabla de productos", "ok", "Que tiendas lleva cada producto")
    for e, d in EXPERTOS.items():
        glob = config.expertos.get(e, d.default_glob)
        destino = ", ".join(softwares_de[e]) or "-"
        if fnmatch.fnmatch(name, glob):
            if e not in habilitados:
                return PlannedFile(name, destino, e, "desactivado", "Experto desactivado en Configuracion")
            if activos.get(e) == path:
                return PlannedFile(name, destino, e, "ok", "Experto del ciclo (fecha mas nueva)")
            if not softwares_de[e]:
                return PlannedFile(name, "-", e, "no-habilitado", "Ningun software habilitado usa este experto")
            return PlannedFile(name, destino, e, "no-habilitado", "No es el mas nuevo - se ignora en este ciclo")
        if path.suffix.lower() == ".xls" and fnmatch.fnmatch(name, glob.split("*", 1)[0] + "*"):
            return PlannedFile(
                name, destino, e, "error", "Formato .xls: tope de 65.535 filas (queda truncado). Guardarlo como .xlsx"
            )
    if name == config.homologos_master_name:
        return PlannedFile(
            name, "-", "-", "no-habilitado", "Homologos por ID (flujo anterior): solo sirve para armar la tabla de productos"
        )
    if fnmatch.fnmatch(name, EXPERT_MASTER_GLOB):
        return PlannedFile(name, "-", "-", "no-habilitado", "Experto xData (flujo anterior): ya no se usa en el ciclo")
    return PlannedFile(name, "-", "-", "error", "Nombre no reconocido por la convencion")
