from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

MAX_COLORANTES = 4


class Colorante(BaseModel):
    codigo: str
    onzas_48: float


class FormulaCanonica(BaseModel):
    linea_producto: str
    origen_archivo: str
    origen_fila: int

    familia: str
    clasificacion: Optional[str] = None

    producto: str
    cartilla: Optional[str] = None
    formato: Optional[str] = None
    tolerancia_luz: Optional[str] = None
    primer: Optional[str] = None
    color: str

    r: Optional[int] = None
    g: Optional[int] = None
    b: Optional[int] = None

    base: Optional[str] = None
    oz_base: Optional[float] = None

    colorantes: list[Colorante] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("colorantes")
    @classmethod
    def _max_colorantes(cls, v: list[Colorante]) -> list[Colorante]:
        if len(v) > MAX_COLORANTES:
            raise ValueError(f"maximo {MAX_COLORANTES} colorantes por formula, se recibieron {len(v)}")
        return v
