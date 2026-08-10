from __future__ import annotations

from pathlib import Path

import openpyxl

from tint_sis.adapters.rows import HEADER, build_row_values
from tint_sis.canonical.models import FormulaCanonica


def write_ajuste_expert_file(formulas: list[FormulaCanonica], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hoja1"
    ws.append(HEADER)
    for formula in formulas:
        ws.append(build_row_values(formula))
    wb.save(output_path)
