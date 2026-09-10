from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Convencion de nombre para el par de archivos del filtro por homologos: el
# archivo experto maestro (todas las lineas de producto, sin filtrar) y el archivo
# de homologos (que trae, por cada tienda/grupo, la lista de IDs que le
# corresponden) se emparejan por compartir el mismo sufijo despues del prefijo,
# p.ej. "expert_test.xlsx" + "homologos_test.xlsx" (sufijo "test"). Convencion
# vieja mantenida para pruebas; el flujo real usa el "maestro fijo" de abajo
# (homologos_TINT.xlsx + xData_DATACOMPLETA_<fecha>.xlsx).
HOMOLOGOS_FILENAME_RE = re.compile(r"^homologos_(?P<sufijo>.+)$", re.IGNORECASE)

# Flujo "maestro fijo": el archivo de homologos NO cambia entre ciclos (solo si
# se agrega una linea/producto nuevo), y el experto llega cada ~15 dias con la
# fecha en el nombre. Los nombres base son distintos y no comparten sufijo, asi
# que el emparejamiento es por convencion fija; si hay varios expertos se toma el
# de fecha mas nueva (fecha DD_MM_YYYY al final del nombre; si no la trae, mtime).
HOMOLOGOS_MASTER_NAME = "homologos_TINT.xlsx"
EXPERT_MASTER_GLOB = "xData_DATACOMPLETA*.xlsx"
_EXPERT_DATE_RE = re.compile(r"_(?P<d>\d{2})_(?P<m>\d{2})_(?P<y>\d{4})$")


@dataclass(frozen=True)
class HomologosExpertPair:
    sufijo: str
    expert_path: Path
    homologos_path: Path


def find_homologos_expert_pairs(input_dir: Path) -> list[HomologosExpertPair]:
    """Busca en input_dir cada homologos_<SUFIJO>.xlsx y lo empareja con su
    expert_<SUFIJO>.xlsx correspondiente. Si no existe el expert con el mismo
    sufijo, ese homologos se ignora (se reporta aparte como advertencia por quien
    llama, aca no se lanza excepcion para no romper el resto del lote)."""
    input_dir = Path(input_dir)
    pairs: list[HomologosExpertPair] = []
    for homologos_path in sorted(input_dir.glob("homologos_*.xlsx")):
        if homologos_path.name == HOMOLOGOS_MASTER_NAME:
            continue  # lo maneja find_homologos_master_pair (experto por fecha)
        match = HOMOLOGOS_FILENAME_RE.match(homologos_path.stem)
        if not match:
            continue
        sufijo = match.group("sufijo")
        expert_path = homologos_path.with_name(f"expert_{sufijo}.xlsx")
        if expert_path.exists():
            pairs.append(HomologosExpertPair(sufijo=sufijo, expert_path=expert_path, homologos_path=homologos_path))
    return pairs


def expert_master_sort_key(path: Path) -> tuple:
    """Clave de orden ascendente: los archivos con fecha DD_MM_YYYY en el nombre
    ordenan por esa fecha (mas nuevo = mayor); los que no traen fecha caen antes
    que cualquiera con fecha y ordenan entre si por mtime. Se usa con
    `reverse=True` donde se quiera "el mas nuevo arriba" (preview.py)."""
    match = _EXPERT_DATE_RE.search(path.stem)
    if match:
        return (1, int(match.group("y")), int(match.group("m")), int(match.group("d")))
    return (0, path.stat().st_mtime, 0, 0)


def find_homologos_master_pair(
    input_dir: Path,
    master_name: str = HOMOLOGOS_MASTER_NAME,
    expert_glob: str = EXPERT_MASTER_GLOB,
) -> HomologosExpertPair | None:
    """Empareja el homologos maestro fijo (homologos_TINT.xlsx) con el archivo
    experto mas reciente (xData_DATACOMPLETA*.xlsx). Devuelve None si falta
    cualquiera de los dos. `master_name` / `expert_glob` se pueden pisar desde
    config."""
    input_dir = Path(input_dir)
    homologos_path = input_dir / master_name
    if not homologos_path.exists():
        return None
    candidates = [p for p in input_dir.glob(expert_glob) if p.name != master_name]
    if not candidates:
        return None
    expert_path = max(candidates, key=expert_master_sort_key)
    return HomologosExpertPair(sufijo="TINT", expert_path=expert_path, homologos_path=homologos_path)
