"""Previsualizacion de un ciclo (dry-run) — plan PLAN_APP_TINT_SIS.md §5.3.

Mira que hay en la carpeta de entrada y clasifica cada .xlsx sin correr el
filtro pesado. Alimenta la vista "Nuevo ciclo".
"""
from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass
from pathlib import Path

from tint_sis.config import AppConfig
from tint_sis.routing import HOMOLOGOS_FILENAME_RE, find_homologos_master_pair


@dataclass
class PlannedFile:
    archivo: str
    software: str  # "xData" | "-"
    flujo: str  # "Filtro por homologos" | "-"
    estado: str  # "ok" | "no-habilitado" | "error"
    detalle: str


@dataclass
class BatchPreview:
    homologos_activo: str | None
    experto_activo: str | None
    tiendas_habilitadas: list[str]
    archivos: list[PlannedFile]
    puede_ejecutar: bool
    bloqueantes: list[str]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["archivos"] = [asdict(f) for f in self.archivos]
        return d


def preview_batch(config: AppConfig) -> BatchPreview:
    input_dir = Path(config.input_dir)
    master_name = config.homologos_master_name
    expert_glob = config.expert_glob

    archivos: list[PlannedFile] = []
    bloqueantes: list[str] = []

    if not input_dir.exists():
        bloqueantes.append(f"La carpeta de entrada no existe: {input_dir}")
        return BatchPreview(None, None, sorted(config.enabled_grupos), [], False, bloqueantes)

    master_pair = find_homologos_master_pair(input_dir, master_name, expert_glob)
    xlsx_files = sorted(
        p for p in input_dir.glob("*.xlsx") if not p.name.startswith("~$")
    )

    for path in xlsx_files:
        name = path.name
        if name == master_name:
            archivos.append(PlannedFile(name, "xData", "-", "ok", "Maestro de homologos"))
        elif master_pair is not None and path == master_pair.expert_path:
            archivos.append(
                PlannedFile(name, "xData", "Filtro por homologos", "ok", "Experto del ciclo (fecha mas nueva)")
            )
        elif fnmatch.fnmatch(name, expert_glob):
            archivos.append(
                PlannedFile(
                    name,
                    "xData",
                    "Filtro por homologos",
                    "no-habilitado",
                    "Experto xData, pero no es el mas nuevo - se ignora en este ciclo",
                )
            )
        elif HOMOLOGOS_FILENAME_RE.match(path.stem):
            archivos.append(
                PlannedFile(name, "xData", "-", "no-habilitado", "Homologos de convencion vieja (por sufijo)")
            )
        else:
            archivos.append(
                PlannedFile(name, "-", "-", "error", "Nombre no reconocido por la convencion")
            )

    if master_pair is None:
        homologos_ok = (input_dir / master_name).exists()
        if not homologos_ok:
            bloqueantes.append(f"Falta el maestro de homologos ({master_name}) en la carpeta de entrada")
        else:
            bloqueantes.append(
                f"No hay ningun archivo experto que matchee '{expert_glob}' en la carpeta de entrada"
            )

    return BatchPreview(
        homologos_activo=master_name if (input_dir / master_name).exists() else None,
        experto_activo=master_pair.expert_path.name if master_pair else None,
        tiendas_habilitadas=sorted(config.enabled_grupos),
        archivos=archivos,
        puede_ejecutar=master_pair is not None,
        bloqueantes=bloqueantes,
    )
