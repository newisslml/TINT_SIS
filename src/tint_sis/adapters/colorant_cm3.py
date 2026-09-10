"""Variante `_cm3` de una salida `_ready.xlsx`.

Genera una copia idéntica del archivo filtrado por tienda, pero con las cantidades
de los primeros 5 colorantes convertidas de "Oz/48" a centímetros cúbicos. En la
hoja esas cantidades viven en las columnas R, T, V, X y Z (0-based 17, 19, 21, 23,
25), es decir `qnt_ml_1`..`qnt_ml_5`.

Conversión pedida por celda:  valor / 48 * 29.574  (redondeado a 3 decimales)
    48     = onzas por unidad (unit_name "USoz/48")
    29.574 = mL por onza líquida US (columna "fraction" del experto)

El resto de las celdas —encabezado, columnas de código de colorante y las demás
`qnt_ml_*`— se copian sin tocar. Se escribe con el camino rápido de openpyxl
(valores planos, sin number_format por celda): el archivo tiene ~160k filas y
esta variante no alimenta ningún CSV, así que no necesita conservar los formatos.
El archivo de origen no se modifica.
"""
from __future__ import annotations

from pathlib import Path

import openpyxl

# Columnas (0-based) cuya cantidad se convierte a cm³: R, T, V, X, Z.
CM3_COLUMNS: tuple[int, ...] = (17, 19, 21, 23, 25)

_OZ_DIVISOR = 48.0
_ML_PER_OZ = 29.574
_DECIMALS = 3


def _to_cm3(value: object) -> object:
    """Convierte una cantidad en Oz/48 a cm³ redondeada a 3 decimales. Deja la
    celda intacta si está vacía o no es numérica (los bool no cuentan como
    número)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return round(value / _OZ_DIVISOR * _ML_PER_OZ, _DECIMALS)


def write_cm3_variant(
    src_xlsx: Path,
    dst_xlsx: Path,
    *,
    columns: tuple[int, ...] = CM3_COLUMNS,
) -> int:
    """Copia `src_xlsx` a `dst_xlsx` convirtiendo a cm³ las cantidades de `columns`
    (0-based). Devuelve la cantidad de filas de datos escritas (sin el encabezado).
    No modifica `src_xlsx`."""
    src_xlsx = Path(src_xlsx)
    dst_xlsx = Path(dst_xlsx)
    dst_xlsx.parent.mkdir(parents=True, exist_ok=True)

    wb_in = openpyxl.load_workbook(src_xlsx, read_only=True, data_only=True)
    ws_in = wb_in[wb_in.sheetnames[0]]
    rows_iter = ws_in.iter_rows(values_only=True)

    wb_out = openpyxl.Workbook(write_only=True)
    ws_out = wb_out.create_sheet(ws_in.title)

    cols = columns
    ws_out.append(list(next(rows_iter)))

    written = 0
    for row in rows_iter:
        out = list(row)
        for idx in cols:
            if idx < len(out):
                out[idx] = _to_cm3(out[idx])
        ws_out.append(out)
        written += 1

    wb_in.close()
    wb_out.save(dst_xlsx)
    return written
