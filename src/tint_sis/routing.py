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
