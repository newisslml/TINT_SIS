from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Convencion de nombre para los archivos expertos que ya vienen en formato final
# (tabla plana con Clasificacion/Producto/... como columnas propias, sin necesidad
# de metadata sidecar): expert<SUFIJO_OPCIONAL>_<GRUPO_DE_TIENDAS>_<MAQUINA_SOFTWARE>.xlsx
# El sufijo opcional (sin guion bajo) permite variantes como expert1_, expertV2_, etc.
EXPERT_FILENAME_RE = re.compile(r"^expert[^_]*_(?P<grupo>[^_]+)_(?P<maquina>.+)$", re.IGNORECASE)

# Maquina (tal como aparece en el nombre de archivo, normalizada a minuscula) ->
# tipo de salida. Se agrega a mano cada maquina nueva una vez confirmado su formato
# real (no se adivina un formato sin un archivo de referencia para validar contra).
MACHINE_OUTPUT_FORMATS: dict[str, str] = {
    "corob4.1.2": "csv_passthrough",
}


@dataclass(frozen=True)
class ExpertFileRoute:
    grupo: str
    maquina: str
    formato_salida: str | None  # None si la maquina no esta registrada todavia


def parse_expert_filename(path: Path) -> ExpertFileRoute | None:
    """Si el archivo sigue la convencion expert_<GRUPO>_<MAQUINA>.xlsx, devuelve a
    que grupo de tiendas y maquina corresponde. Si no matchea (p.ej. expert.xlsx,
    test5.xlsx), devuelve None y el archivo sigue el flujo clasico FORMULARIO +
    metadata sidecar."""
    match = EXPERT_FILENAME_RE.match(Path(path).stem)
    if not match:
        return None
    grupo = match.group("grupo")
    maquina = match.group("maquina")
    formato = MACHINE_OUTPUT_FORMATS.get(maquina.lower())
    return ExpertFileRoute(grupo=grupo, maquina=maquina, formato_salida=formato)


# Convencion de nombre para el par de archivos del filtro por homologos: el
# archivo experto maestro (todas las lineas de producto, sin filtrar) y el archivo
# de homologos (que trae, por cada tienda/grupo, la lista de IDs que le
# corresponden) se emparejan por compartir el mismo sufijo despues del prefijo,
# p.ej. "expert_test.xlsx" + "homologos_test.xlsx" (sufijo "test"), o en un ciclo
# real "expert_2026_09.xlsx" + "homologos_2026_09.xlsx". Se distingue a proposito
# de expert_<GRUPO>_<MAQUINA>.xlsx (arriba): ese ya viene pre-filtrado por tienda,
# este es el maestro completo que hay que filtrar.
HOMOLOGOS_FILENAME_RE = re.compile(r"^homologos_(?P<sufijo>.+)$", re.IGNORECASE)


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
        match = HOMOLOGOS_FILENAME_RE.match(homologos_path.stem)
        if not match:
            continue
        sufijo = match.group("sufijo")
        expert_path = homologos_path.with_name(f"expert_{sufijo}.xlsx")
        if expert_path.exists():
            pairs.append(HomologosExpertPair(sufijo=sufijo, expert_path=expert_path, homologos_path=homologos_path))
    return pairs
