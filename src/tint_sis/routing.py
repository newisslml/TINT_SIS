from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

# Los archivos expertos llegan cada ~15 dias; puede haber varios del mismo
# experto en la carpeta (Experto_3_03_09_2026.xlsx, Experto_3_18_09_2026.xlsx) y
# gana el de fecha mas nueva (fecha DD_MM_YYYY al final del nombre; si no la
# trae, por mtime).
_EXPERT_DATE_RE = re.compile(r"_(?P<d>\d{2})_(?P<m>\d{2})_(?P<y>\d{4})$")

# Flujo anterior (cruce por ID_TINT): homologos_TINT.xlsx + el experto xData con
# la columna ID_TINT. Ya no participa del ciclo; lo usan el editor de homologos
# (cobertura) y `cli productos-init` para armar la tabla de productos.
HOMOLOGOS_MASTER_NAME = "homologos_TINT.xlsx"
EXPERT_MASTER_GLOB = "xData_DATACOMPLETA*.xlsx"


@dataclass(frozen=True)
class HomologosExpertPair:
    sufijo: str
    expert_path: Path
    homologos_path: Path


def expert_master_sort_key(path: Path) -> tuple:
    """Clave de orden ascendente: los archivos con fecha DD_MM_YYYY en el nombre
    ordenan por esa fecha (mas nuevo = mayor); los que no traen fecha caen antes
    que cualquiera con fecha y ordenan entre si por mtime. Se usa con
    `reverse=True` donde se quiera "el mas nuevo arriba" (preview.py)."""
    match = _EXPERT_DATE_RE.search(path.stem)
    if match:
        return (1, int(match.group("y")), int(match.group("m")), int(match.group("d")))
    return (0, path.stat().st_mtime, 0, 0)


def matching_files(input_dir: Path, glob: str) -> list[Path]:
    """Archivos de `input_dir` que matchean `glob` (sin los temporales ~$ de Excel)."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        return []
    return [
        p
        for p in input_dir.iterdir()
        if p.is_file() and not p.name.startswith("~$") and fnmatch.fnmatch(p.name, glob)
    ]


def find_latest_expert(input_dir: Path, glob: str) -> Path | None:
    """El archivo mas nuevo de `input_dir` que matchea `glob`, o None."""
    candidates = matching_files(input_dir, glob)
    if not candidates:
        return None
    return max(candidates, key=expert_master_sort_key)


def find_homologos_master_pair(
    input_dir: Path,
    master_name: str = HOMOLOGOS_MASTER_NAME,
    expert_glob: str = EXPERT_MASTER_GLOB,
) -> HomologosExpertPair | None:
    """Empareja el homologos maestro fijo (homologos_TINT.xlsx) con el experto
    xData mas reciente (xData_DATACOMPLETA*.xlsx). Devuelve None si falta
    cualquiera de los dos."""
    input_dir = Path(input_dir)
    homologos_path = input_dir / master_name
    if not homologos_path.exists():
        return None
    candidates = [p for p in matching_files(input_dir, expert_glob) if p.name != master_name]
    if not candidates:
        return None
    expert_path = max(candidates, key=expert_master_sort_key)
    return HomologosExpertPair(sufijo="TINT", expert_path=expert_path, homologos_path=homologos_path)
