from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from openpyxl.cell import WriteOnlyCell

from tint_sis.adapters.passthrough_csv import write_passthrough_csv

# Los grupos/tiendas se habilitan a mano una vez confirmado que su hoja en el
# archivo de homologos y su cruce contra el experto quedaron completos (mismo
# criterio cauteloso que MACHINE_OUTPUT_FORMATS en routing.py: no se adivina).
ENABLED_GRUPOS = {"MP12"}

ID_RE = re.compile(r"^TINT\d+$")


def read_homologos_ids(path: Path, grupo: str) -> set[str]:
    """Extrae el set de IDs TINT### presentes en cualquier celda de la hoja
    `grupo` del archivo de homologos. No asume una columna fija: la hoja real
    intercala los IDs con filas de encabezado/categoria en columnas variables."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[grupo]
        ids: set[str] = set()
        for row in ws.iter_rows(values_only=True):
            for value in row:
                if isinstance(value, str) and ID_RE.match(value.strip()):
                    ids.add(value.strip())
        return ids
    finally:
        wb.close()


def filter_expert_by_ids(expert_path: Path, ids: set[str], output_xlsx_path: Path) -> int:
    """Copia de expert_path (columna A = ID) solo las filas cuyo ID esta en
    `ids`, preservando el number_format original de cada celda (lo necesita
    write_passthrough_csv despues para formatear fechas/decimales igual que en
    el resto del flujo). No modifica expert_path, solo lo lee.

    Devuelve la cantidad de filas de datos escritas (sin contar encabezado).
    """
    output_xlsx_path = Path(output_xlsx_path)
    output_xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    wb_in = openpyxl.load_workbook(expert_path, read_only=True, data_only=True)
    ws_in = wb_in[wb_in.sheetnames[0]]
    rows_iter = ws_in.iter_rows()

    header = [c.value for c in next(rows_iter)]

    wb_out = openpyxl.Workbook(write_only=True)
    ws_out = wb_out.create_sheet(wb_in.sheetnames[0])
    ws_out.append(header)

    written = 0
    for row in rows_iter:
        id_value = row[0].value
        if id_value is None or str(id_value).strip() not in ids:
            continue
        written += 1
        out_row = []
        for cell in row:
            out_cell = WriteOnlyCell(ws_out, value=cell.value)
            # cell.number_format puede volver None para celdas nunca formateadas
            # explicitamente en el origen; "General" es el default real de Excel.
            out_cell.number_format = cell.number_format or "General"
            out_row.append(out_cell)
        ws_out.append(out_row)

    wb_in.close()
    wb_out.save(output_xlsx_path)
    return written


@dataclass(frozen=True)
class HomologosFilterResult:
    grupo: str
    filas_filtradas: int
    xlsx_path: Path
    csv_path: Path


def run_homologos_filter(
    expert_path: Path,
    homologos_path: Path,
    output_dir: Path,
) -> tuple[list[HomologosFilterResult], list[str]]:
    """Por cada hoja (grupo/tienda) del archivo de homologos que este habilitada
    en ENABLED_GRUPOS, filtra expert_path por los IDs de esa hoja y genera
    <grupo>_ready.xlsx + <grupo>_ready.csv en output_dir. Ninguno de los dos
    archivos de entrada se modifica, solo se leen como referencia."""
    output_dir = Path(output_dir)
    results: list[HomologosFilterResult] = []
    warnings: list[str] = []

    wb_h = openpyxl.load_workbook(homologos_path, read_only=True, data_only=True)
    sheet_names = list(wb_h.sheetnames)
    wb_h.close()

    for grupo in sheet_names:
        if grupo not in ENABLED_GRUPOS:
            warnings.append(
                f"{homologos_path.name}: hoja '{grupo}' encontrada pero el grupo "
                "todavia no esta habilitado para el filtro (agregar a "
                "ENABLED_GRUPOS en adapters/homologos_filter.py una vez "
                "confirmado el cruce de IDs) - se omite"
            )
            continue

        ids = read_homologos_ids(homologos_path, grupo)
        if not ids:
            warnings.append(
                f"{homologos_path.name}: hoja '{grupo}' no tiene ningun ID "
                "TINT### - se omite"
            )
            continue

        xlsx_path = output_dir / f"{grupo}_ready.xlsx"
        csv_path = output_dir / f"{grupo}_ready.csv"

        filas = filter_expert_by_ids(expert_path, ids, xlsx_path)
        write_passthrough_csv(xlsx_path, csv_path)

        results.append(
            HomologosFilterResult(
                grupo=grupo,
                filas_filtradas=filas,
                xlsx_path=xlsx_path,
                csv_path=csv_path,
            )
        )

    return results, warnings
