"""Archivo maestro de tintometria ("Todo MP14 <DDMMAAAA>.xlsx"): el experto padre
del que salen los 3 archivos expertos de un ciclo.

Tiene el formato de Experto 1 (Color Pro): una hoja con Clasificacion, Producto,
Cartilla, Formato, Tolerancia luz, Primer, Color, R, G, B, Base, Oz base y
Col.N-1/48 onzas = "AO-26.5" (codigo y cantidad juntos, en 1/48 oz por envase del
Formato). Una formula se identifica por CLAVE_FORMULA (Clasificacion, Producto,
Cartilla, Color y Base); las filas con una clave ya vista son duplicadas y no
pasan a ningun experto. Experto 3 no lleva cartilla, asi que ahi la clave es
CLAVE_FORMULA_E3 (sin Cartilla): de un mismo color en varias cartillas queda la
primera fila. Reglas verificadas fila a fila contra los expertos del
24/09/2026 (174.127 formulas iguales en los 3):

  Experto 1  el maestro tal cual (copia del archivo, sin las duplicadas), salvo
             las formulas que no vienen en galon (`a_galon`).
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

Los 3 expertos van siempre por galon (pedido del usuario: E2/E3 el 28/09/2026,
tambien E1 el 01/10/2026): una formula en "Tineta 4 gl" trae las cantidades
para 4 galones (en Texturex son exactamente 4 veces las de sus homologos en
galon; 53.706 pares verificados), asi que se divide por los galones del envase.
En E1 la fila queda con Formato "Galon" y Oz base y colorantes divididos. Los
galones de cada formato salen de FORMATOS_GALONES o, si no esta ahi, de la
cantidad que dice su nombre ("Balde 5 gl", "1/4 galon", "1 litro"; se avisa).
Un formato sin equivalencia en ninguno de los dos bloquea la preparacion.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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
LITROS_POR_GALON = 3.785
# cantidad y unidad en el nombre normalizado de un formato que no esta en
# FORMATOS_GALONES: "balde5gl", "1/4galon", "litro" (sin numero = 1)
_FORMATO_CANTIDAD_RE = re.compile(
    r"(?:(\d+(?:[.,]\d+)?)(?:/(\d+))?)?(galones|galon|gal|gl|litros|litro|lts|lt)(?![a-z])"
)

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
    "oz_base": "ozbase",
}
# una formula = un color de un producto: dos filas con la misma clave son la misma
# formula aunque cambien RGB, notas, formato o colorantes (se deja la primera)
CLAVE_FORMULA = ("clasificacion", "producto", "cartilla", "color", "base")
# Experto 3 no lleva cartilla: el mismo color en dos cartillas es la misma formula
CLAVE_FORMULA_E3 = ("clasificacion", "producto", "color", "base")
OBLIGATORIAS = ("clasificacion", "producto", "cartilla", "formato", "color", "base")
_COLORANTE_ENC_RE = re.compile(r"^col\.?(\d+)-1/48onzas$")
_COLORANTE_RE = re.compile(r"^([A-Za-z]{1,4})\s*-\s*(\d+(?:[.,]\d+)?)$")
# la celda tal como viene, para cambiar solo la cantidad: " oc - 3,5 " -> (" oc - ", "3,5", " ")
_COLORANTE_PARTES_RE = re.compile(r"^(\s*[A-Za-z]{1,4}\s*-\s*)(\d+(?:[.,]\d+)?)(\s*)$")
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


def equivalencia(formato: object) -> tuple[float | None, bool]:
    """(galones que contiene el envase, si salio del nombre del formato y no de
    FORMATOS_GALONES). (None, False) si no se sabe."""
    clave = normalizar(formato)
    if clave in FORMATOS_GALONES:
        return FORMATOS_GALONES[clave], False
    m = _FORMATO_CANTIDAD_RE.search(clave)
    # sin numero solo vale la unidad sola ("Litro"): "Cuarto de galon" no es 1 galon
    if m is None or (not m.group(1) and m.group(0) != clave):
        return None, False
    numero, divisor, unidad = m.groups()
    cantidad = float(numero.replace(",", ".")) if numero else 1.0
    if divisor:
        cantidad /= int(divisor) or 1
    if unidad.startswith("l"):
        cantidad /= LITROS_POR_GALON
    return (cantidad if cantidad > 0 else None), cantidad > 0


def galones(formato: object) -> float | None:
    return equivalencia(formato)[0]


def _dividir(cantidad: str, galones_envase: float) -> Decimal | None:
    """cantidad (texto con . o ,) / galones, en decimal exacto (26.5 / 4 = 6.625)
    con a lo sumo 6 decimales. None si no es un numero."""
    try:
        q = Decimal(cantidad.strip().replace(",", ".")) / Decimal(str(galones_envase))
    except (InvalidOperation, ZeroDivisionError):
        return None
    if q.as_tuple().exponent < -6:
        q = q.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return q.normalize()


def _decimal_texto(q: Decimal) -> str:
    return format(q, "f")


def a_galon(cols: "Columnas", fila: list) -> dict[int, str | int | float]:
    """Celdas a cambiar para dejar por galon una formula del maestro en Experto
    1 (posicion de columna -> valor nuevo): Formato "Galon" y Oz base y la
    cantidad de cada colorante divididos por los galones del envase ("OC-62.8"
    en Tineta 4 gl -> "OC-15.7"; el codigo y la grafia de la celda se
    conservan). {} si ya esta en galon o el formato no tiene equivalencia."""
    galones_envase = galones(cols.valor(fila, "formato"))
    if galones_envase is None or galones_envase == 1:
        return {}
    cambios: dict[int, str | int | float] = {cols.pos["formato"]: CAN_GALON}
    oz = cols.valor(fila, "oz_base")
    if oz is not None and str(oz).strip():
        q = _dividir(str(oz), galones_envase)
        if q is not None:
            cambios[cols.pos["oz_base"]] = int(q) if q == q.to_integral_value() else float(q)
    for i in cols.colorantes:
        celda = fila[i] if i < len(fila) else None
        if parse_colorante(celda) is None:  # vacia ("-0"): queda igual
            continue
        prefijo, cantidad, cola = _COLORANTE_PARTES_RE.match(str(celda)).groups()
        texto = _decimal_texto(_dividir(cantidad, galones_envase))
        cambios[i] = prefijo + (texto.replace(".", ",") if "," in cantidad else texto) + cola
    return cambios


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

    def clave_formula(self, fila: list, campos: tuple[str, ...] = CLAVE_FORMULA) -> tuple[str, ...]:
        """Clasificacion, Producto, Cartilla, Color y Base (o `campos`) sin
        acentos, mayusculas ni espacios: dos filas con la misma clave son la
        misma formula."""
        return tuple(normalizar(self.valor(fila, c)) for c in campos)


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
