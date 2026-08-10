from __future__ import annotations

import csv
from pathlib import Path

from tint_sis.adapters.rows import HEADER, build_row_values
from tint_sis.canonical.models import FormulaCanonica

ENCODING = "iso-8859-1"
LINE_TERMINATOR = "\r\n"

__all__ = ["HEADER", "write_coroblab_file"]


# Confirmado contra formato_final.txt (referencia real): sin ceros de relleno ni
# punto decimal en enteros ("128", "7", "0.5", "86.5"), nunca "128.00" ni "7.00".
def _fmt_number(value) -> str:
    if isinstance(value, float):
        rounded = round(value, 2)
        if rounded == int(rounded):
            return str(int(rounded))
        return f"{rounded:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _fmt_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return _fmt_number(value)
    return str(value)


def _row(formula: FormulaCanonica) -> list[str]:
    return [_fmt_value(v) for v in build_row_values(formula)]


def write_coroblab_file(formulas: list[FormulaCanonica], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding=ENCODING, newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator=LINE_TERMINATOR)
        writer.writerow(HEADER)
        for formula in formulas:
            writer.writerow(_row(formula))
