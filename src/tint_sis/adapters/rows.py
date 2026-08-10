from __future__ import annotations

from tint_sis.canonical.models import FormulaCanonica

MAX_COLORANTES = 4

HEADER = [
    "Clasificacion",
    "Producto",
    "Cartilla",
    "Formato",
    "Tolerancia Luz",
    "Primer",
    "Color",
    "R",
    "G",
    "B",
    "Base",
    "Oz Base",
    "Col. 1",
    "1/48 onzas",
    "Col. 2",
    "1/48 onzas",
    "Col. 3",
    "1/48 onzas",
    "Col. 4",
    "1/48 onzas",
]


def _excel_number(value):
    if value is None:
        return None
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def build_row_values(formula: FormulaCanonica) -> list:
    row = [
        formula.clasificacion,
        formula.producto,
        formula.cartilla,
        formula.formato,
        formula.tolerancia_luz,
        formula.primer,
        formula.color,
        formula.r,
        formula.g,
        formula.b,
        formula.base,
        _excel_number(formula.oz_base),
    ]
    n_used = len(formula.colorantes)
    for i in range(MAX_COLORANTES):
        if i < n_used:
            colorante = formula.colorantes[i]
            row.append(colorante.codigo)
            row.append(_excel_number(colorante.onzas_48))
        else:
            row.append(None)
            # Quirk confirmado contra ajuste_expert.xlsx / formato_final.txt (2312
            # filas reales): un slot de colorante sin usar muestra 0 en la cantidad,
            # salvo el ultimo (Col. 4), que siempre queda en blanco.
            row.append(None if i == MAX_COLORANTES - 1 else 0)
    return row
