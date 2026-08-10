from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class LineaMetadata(BaseModel):
    clasificacion: str
    producto: str
    cartilla: str
    formato: str


def sidecar_path_for(excel_path: Path) -> Path:
    return Path(excel_path).with_suffix(".json")


def load_linea_metadata(path: Path) -> LineaMetadata:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LineaMetadata(**data)
