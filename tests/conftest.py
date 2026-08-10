from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from tint_sis.ingestion.linea_metadata import LineaMetadata

# Estructura confirmada contra el expert.xlsx real: encabezado en la fila 39, datos
# desde la 40, 50 columnas relevantes (FAMILIA..COSTO del ultimo colorante). El
# encabezado "R" se repite 5 veces (RGB + una por cada bloque de colorante) y la
# cantidad real de cada colorante esta 3 columnas a la derecha de "COL_n", no al lado.
HEADER_ROW = 39
HEADERS = [
    "FAMILIA", "PRODUCTO", "CARTILLA", "FORMATO", "TOLERANCIA LUZ", "PRIMER", "COLOR",
    "R", "G", "B",
    "REVISADO EN AT", "RESULTADO DE CMC ", "VERSION", "RESPONSABLE", "Observaciones",
    "BASE", "Oz base", "gr/100 ml",
] + [
    h
    for _ in range(4)
    for h in ["COL_1", "Y", "R", "1/48 onzas", "Total Onzas galon", "ml galon", "ml 100 ml", "COSTO"]
]
# COL_1..COL_4 deben ser distintos entre bloques (no todos "COL_1"); se corrige abajo.
for _block, _start in enumerate((18, 26, 34, 42)):
    HEADERS[_start] = f"COL_{_block + 1}"


def _colorante_block(codigo, qty):
    if codigo is None:
        return [None, None, None, 0, 0, 0, 0, 0]
    return [codigo, None, qty, qty, 0, 0, 0, 0]


ROWS = [
    ["Latex", "Latex Experto y Homologos", "L. Experto ", "Galon", "-", "-", "Blanco Tecnoconstrucción ",
     255, 255, 255, None, None, None, None, None,
     "BT", 100.0, 0]
    + _colorante_block("AM01", 2.5)
    + _colorante_block("NG01", 0.75)
    + _colorante_block(None, None)
    + _colorante_block(None, None),
    ["Latex", "Latex Experto y Homologos", "L. Experto ", "Galon", "-", "-", "Rojo Ñuble",
     200, 10, 10, None, None, None, None, None,
     "BT", 95.5, 0]
    + _colorante_block("RO02", 4.0)
    + _colorante_block(None, None)
    + _colorante_block(None, None)
    + _colorante_block(None, None),
    ["Esmalte", "Esmalte Sintetico", "Cartilla Esmalte", "Galon", "-", "-", "Azul Marino",
     300, 20, 20, None, None, None, None, None,
     "BS", 80.0, 0]
    + _colorante_block("AZ03", 1.2)
    + _colorante_block("NG01", 0.5)
    + _colorante_block("BL01", 0.25)
    + _colorante_block(None, None),
]


def _build_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "FORMULARIO "

    ws.cell(row=1, column=1, value="FORMULARIO TINTOMETRICO (encabezado auxiliar, no forma parte de la tabla)")

    for col_idx, header in enumerate(HEADERS, start=1):
        ws.cell(row=HEADER_ROW, column=col_idx, value=header)

    for row_offset, row_values in enumerate(ROWS):
        row_idx = HEADER_ROW + 1 + row_offset
        for col_idx, value in enumerate(row_values, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    wb.save(path)


@pytest.fixture
def sample_excel(tmp_path: Path) -> Path:
    path = tmp_path / "Latex Experto y Homologos.xlsx"
    _build_workbook(path)
    return path


@pytest.fixture
def linea_metadata() -> LineaMetadata:
    return LineaMetadata(
        clasificacion="1.-Latex",
        producto="Ltx.Extracubriente Sipa/Ltx.Tecnoconstrucción Sipa (test)",
        cartilla="Cartilla Ltx. Extracubriente",
        formato="Galon (3.785 Lts.)",
    )


@pytest.fixture
def sample_excel_with_metadata(sample_excel: Path, linea_metadata: LineaMetadata) -> Path:
    sidecar = sample_excel.with_suffix(".json")
    sidecar.write_text(json.dumps(linea_metadata.model_dump(), ensure_ascii=False), encoding="utf-8")
    return sample_excel
