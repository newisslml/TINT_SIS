"""Archivo maestro de tintometria ("Todo MP14 <DDMMAAAA>.xlsx"): el experto padre
del que salen los 3 archivos expertos de un ciclo.

Tiene el formato de Experto 1 (Color Pro): una hoja con Clasificacion, Producto,
Cartilla, Formato, Tolerancia luz, Primer, Color, R, G, B, Base, Oz base y
Col.N-1/48 onzas = "AO-26.5" (codigo y cantidad juntos, en 1/48 oz por envase del
Formato). Reglas verificadas fila a fila contra los expertos del 24/09/2026
(174.127 formulas iguales en los 3):

  Experto 1  el maestro tal cual (copia del archivo).
  Experto 3  Santint/Corob: group_code / product_code de la tabla de productos,
             color_key1 = Color, comment = Tolerancia luz, base_code = Base con la
             grafia de las bases que ya conoce ("BASE N" -> "Base N", "fuerte" ->
             "Fuerte"), can_code "Galon", unit_name USoz/48, unit 29,574,
             fraction 48, weightmode 0, color_r/g/b y colorant_N / qnt_ml_N en
             1/48 oz por galon.
  Experto 2  Tintwise Lab: Clasificacion (con la grafia de la plantilla),
             Producto (nombre de la tabla), Cartilla, Color y Base tal cual,
             Base_Qty 3785, ColN = " AO" (con un espacio adelante, como el
             original), QtyN en cm3 (1/48 oz x 29,574 / 48), R/G/B,
             Note1 = Tolerancia luz y Note2 = Primer.

Las cantidades de E2/E3 van por galon: una formula en "Tineta 4 gl" trae las
cantidades para 4 galones (en Texturex son exactamente 4 veces las de sus
homologos en galon; 53.706 pares verificados), asi que se divide por
FORMATOS_GALONES. Un formato que no este ahi bloquea la preparacion (no se
adivina).
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from tint_sis.adapters.sheet_filter import FormatoExpertoError, iterar_filas
from tint_sis.expertos import normalizar

# ml por onza US y fraccion (1/48 oz) con que trabajan los expertos
ML_POR_ONZA = 29.574
FRACCION = 48
# Base_Qty de Experto 2 y can_code de Experto 3: todo sale en galon
ML_GALON = 3785
CAN_GALON = "Galon"
UNIDAD_E3 = "USoz/48"

# Formato del maestro (normalizado) -> galones que contiene el envase.
FORMATOS_GALONES: dict[str, float] = {
    normalizar("Galon"): 1,
    normalizar("Galon (3.785 Lts.)"): 1,
    normalizar("Tineta 4 gl"): 4,
}

# campo -> encabezado normalizado en el maestro
COLUMNAS = {
    "clasificacion": "clasificacion",
    "producto": "producto",
    "cartilla": "cartilla",
    "formato": "formato",
    "tolerancia": "tolerancialuz",
    "primer": "primer",
    "color": "color",
    "r": "r",
    "g": "g",
    "b": "b",
    "base": "base",
}
OBLIGATORIAS = ("clasificacion", "producto", "formato", "color", "base")
_COLORANTE_ENC_RE = re.compile(r"^col\.?(\d+)-1/48onzas$")
_COLORANTE_RE = re.compile(r"^([A-Za-z]{1,4})\s*-\s*(\d+(?:[.,]\d+)?)$")
# celdas de colorante vacias: "", "-", "-0", "0"
_VACIO_RE = re.compile(r"^-?\s*0*(?:[.,]0*)?$")


class ColoranteError(ValueError):
    """Celda de colorante que no tiene la forma CODIGO-CANTIDAD."""


def parse_colorante(celda: object) -> tuple[str, float] | None:
    """"AO-26.5" -> ("AO", 26.5); None si la celda esta vacia ("", "-0"). El
    codigo va en mayusculas (el maestro trae algunos "oc", "rj")."""
    if celda is None:
        return None
    texto = str(celda).strip()
    if not texto or _VACIO_RE.match(texto):
        return None
    m = _COLORANTE_RE.match(texto)
    if not m:
        raise ColoranteError(texto)
    return m.group(1).upper(), float(m.group(2).replace(",", "."))


def galones(formato: object) -> float | None:
    return FORMATOS_GALONES.get(normalizar(formato))


@dataclass(frozen=True)
class Columnas:
    """Posicion de cada campo en la hoja del maestro."""

    pos: dict[str, int]
    colorantes: tuple[int, ...]  # posiciones de Col.1, Col.2, ... en orden

    @classmethod
    def desde_encabezado(cls, encabezado: list[object], archivo: str = "maestro") -> "Columnas":
        normal = [normalizar(h) for h in encabezado]
        pos: dict[str, int] = {}
        for campo, enc in COLUMNAS.items():
            if enc in normal:
                pos[campo] = normal.index(enc)
        colorantes = sorted(
            ((int(m.group(1)), i) for i, h in enumerate(normal) if (m := _COLORANTE_ENC_RE.match(h))),
        )
        faltan = [COLUMNAS[c] for c in OBLIGATORIAS if c not in pos]
        if faltan or not colorantes:
            detalle = ", ".join(faltan + ([] if colorantes else ["Col.N-1/48 onzas"]))
            raise FormatoExpertoError(
                f"{archivo}: no tiene el formato del maestro (Experto 1); faltan las columnas {detalle}"
            )
        return cls(pos=pos, colorantes=tuple(i for _, i in colorantes))

    def valor(self, fila: list, campo: str) -> str | None:
        i = self.pos.get(campo)
        if i is None or i >= len(fila):
            return None
        return fila[i]

    def celdas_colorante(self, fila: list) -> list[object]:
        return [fila[i] if i < len(fila) else None for i in self.colorantes]


def leer(
    path: Path, *, on_progress: Callable[[dict], None] | None = None
) -> tuple[Columnas, Iterator[list]]:
    """(columnas, filas de datos) del maestro, leyendo en streaming."""
    filas = iterar_filas(Path(path), on_progress=on_progress)
    encabezado = next(filas, None)
    if encabezado is None:
        raise FormatoExpertoError(f"{Path(path).name} esta vacio")
    return Columnas.desde_encabezado(encabezado, Path(path).name), filas


def numero(valor: object) -> int | float | str | None:
    """Celda numerica del maestro (R, G, B vienen como texto crudo) -> int/float;
    si no es un numero se deja el texto."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        n = float(texto.replace(",", "."))
    except ValueError:
        return texto
    return int(n) if n.is_integer() else n


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor)
    return texto if texto.strip() else None


# --------------------------------------------------------------------------- #
# conversion por formula
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class NombresProducto:
    """Como se llama un producto del maestro en Experto 2 y 3."""

    e2: str
    e3_grupo: str
    e3_producto: str


class Plantilla:
    """Encabezado de la hoja de formulas de un experto plantilla: posicion de
    cada columna (primera aparicion; Experto 2 repite "Color") y cuantos
    colorantes admite."""

    def __init__(self, encabezado: list[object], prefijo_colorante: str, prefijo_cantidad: str):
        self.ancho = len(encabezado)
        self.pos: dict[str, int] = {}
        for i, h in enumerate(encabezado):
            if h is not None and str(h).strip():
                self.pos.setdefault(normalizar(h), i)
        self.col = prefijo_colorante
        self.qty = prefijo_cantidad
        n = 0
        while f"{self.col}{n + 1}" in self.pos and f"{self.qty}{n + 1}" in self.pos:
            n += 1
        self.max_colorantes = n

    def faltantes(self, campos: tuple[str, ...]) -> list[str]:
        return [c for c in campos if c not in self.pos]

    def fila(self, valores: Mapping[str, object], colorantes: list[tuple[object, object]]) -> list:
        fila: list = [None] * self.ancho
        for campo, valor in valores.items():
            fila[self.pos[campo]] = valor
        for n, (codigo, cantidad) in enumerate(colorantes, start=1):
            fila[self.pos[f"{self.col}{n}"]] = codigo
            fila[self.pos[f"{self.qty}{n}"]] = cantidad
        return fila


CAMPOS_E3 = (
    "group_code", "product_code", "color_key1", "comment", "base_code", "can_code",
    "unit_name", "unit", "fraction", "weightmode", "color_r", "color_g", "color_b",
)
CAMPOS_E2 = ("clasificacion", "producto", "cartilla", "color", "base", "base_qty", "r", "g", "b", "note1", "note2")


def plantilla_e3(encabezado: list[object]) -> Plantilla:
    return Plantilla(encabezado, "colorant_", "qnt_ml_")


def plantilla_e2(encabezado: list[object]) -> Plantilla:
    return Plantilla(encabezado, "col", "qty")


def colorantes_por_galon(celdas: list[object], galones_envase: float) -> list[tuple[str, float]]:
    """Colorantes de una formula en 1/48 oz por galon (lanza ColoranteError)."""
    out = []
    for celda in celdas:
        c = parse_colorante(celda)
        if c is not None:
            codigo, cantidad = c
            out.append((codigo, round(cantidad / galones_envase, 9)))
    return out


def fila_e3(
    cols: Columnas,
    fila: list,
    nombres: NombresProducto,
    base: str | None,
    colorantes: list[tuple[str, float]],
    plantilla: Plantilla,
) -> list:
    valores = {
        "group_code": nombres.e3_grupo,
        "product_code": nombres.e3_producto,
        "color_key1": _texto(cols.valor(fila, "color")),
        "comment": _texto(cols.valor(fila, "tolerancia")),
        "base_code": base,
        "can_code": CAN_GALON,
        "unit_name": UNIDAD_E3,
        "unit": ML_POR_ONZA,
        "fraction": FRACCION,
        "weightmode": 0,
        "color_r": numero(cols.valor(fila, "r")),
        "color_g": numero(cols.valor(fila, "g")),
        "color_b": numero(cols.valor(fila, "b")),
    }
    return plantilla.fila(valores, colorantes)


def fila_e2(
    cols: Columnas,
    fila: list,
    nombres: NombresProducto,
    clasificacion: str | None,
    colorantes: list[tuple[str, float]],
    plantilla: Plantilla,
) -> list:
    valores = {
        "clasificacion": clasificacion,
        "producto": nombres.e2,
        "cartilla": _texto(cols.valor(fila, "cartilla")),
        "color": _texto(cols.valor(fila, "color")),
        "base": _texto(cols.valor(fila, "base")),
        "base_qty": ML_GALON,
        "r": numero(cols.valor(fila, "r")),
        "g": numero(cols.valor(fila, "g")),
        "b": numero(cols.valor(fila, "b")),
        "note1": _texto(cols.valor(fila, "tolerancia")),
        "note2": _texto(cols.valor(fila, "primer")),
    }
    en_cm3 = [(" " + codigo, round(cantidad * ML_POR_ONZA / FRACCION, 9)) for codigo, cantidad in colorantes]
    return plantilla.fila(valores, en_cm3)
