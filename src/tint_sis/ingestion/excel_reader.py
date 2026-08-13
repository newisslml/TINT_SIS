from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from pydantic import ValidationError

from tint_sis.canonical.models import Colorante, FormulaCanonica
from tint_sis.ingestion.linea_metadata import LineaMetadata, load_linea_metadata, sidecar_path_for
from tint_sis.routing import parse_expert_filename

SHEET_NAME_HINT = "FORMULARIO"

# Encabezados esperados, normalizados (mayusculas, espacios simples). "producto",
# "cartilla" y "formato" se leen del crudo solo para guardarlos como metadata de
# auditoria: el valor que va al archivo final sale de LineaMetadata (ver Fase 2.5 /
# hallazgo real: esos 3 campos + Clasificacion son un "sello" fijo por linea de
# producto, no se derivan fila a fila del Excel).
HEADER_ALIASES: dict[str, list[str]] = {
    "familia": ["FAMILIA"],
    "producto": ["PRODUCTO"],
    "cartilla": ["CARTILLA"],
    "formato": ["FORMATO"],
    "tolerancia_luz": ["TOLERANCIA LUZ"],
    "primer": ["PRIMER"],
    "color": ["COLOR"],
    "r": ["R"],
    "g": ["G"],
    "b": ["B"],
    "base": ["BASE"],
    "oz_base": ["OZ BASE"],
}
COLORANTE_FIELDS = ["col_1", "col_2", "col_3", "col_4"]
COLORANTE_ALIASES: dict[str, list[str]] = {
    "col_1": ["COL 1", "COL_1", "COLORANTE 1"],
    "col_2": ["COL 2", "COL_2", "COLORANTE 2"],
    "col_3": ["COL 3", "COL_3", "COLORANTE 3"],
    "col_4": ["COL 4", "COL_4", "COLORANTE 4"],
}
# Distancia confirmada contra expert.xlsx real: cada colorante ocupa un bloque de 8
# columnas (COL_n, Y, R, "1/48 onzas", Total Onzas galon, ml galon, ml 100 ml, COSTO).
# La cantidad real esta 3 columnas a la derecha de COL_n, no inmediatamente al lado.
QUANTITY_OFFSET = 3

REQUIRED_FOR_HEADER_DETECTION = {"FAMILIA", "PRODUCTO", "COLOR", "BASE"}


def _normalize(value) -> str:
    text = "" if value is None else str(value)
    text = text.strip().upper()
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text)


@dataclass
class IngestResult:
    formulas: list[FormulaCanonica] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _pick_sheet(wb):
    for name in wb.sheetnames:
        if SHEET_NAME_HINT in _normalize(name):
            return wb[name]
    return wb[wb.sheetnames[0]]


def _find_header_row(ws, max_scan_rows: int = 100) -> int:
    best_row, best_score = None, 0
    scan_limit = min(max_scan_rows, ws.max_row or max_scan_rows)
    for row_idx in range(1, scan_limit + 1):
        values = {_normalize(c.value) for c in ws[row_idx] if c.value is not None}
        score = len(REQUIRED_FOR_HEADER_DETECTION & values)
        if score > best_score:
            best_score, best_row = score, row_idx
    if best_row is None or best_score < 3:
        raise ValueError("No se pudo detectar la fila de encabezado (se esperaban columnas como FAMILIA, PRODUCTO, COLOR, BASE)")
    return best_row


def _find_column(ws, header_row: int, aliases: list[str]) -> int | None:
    alias_set = set(aliases)
    for cell in ws[header_row]:
        if cell.value is not None and _normalize(cell.value) in alias_set:
            return cell.column
    return None


def _build_column_map(ws, header_row: int) -> dict[str, int]:
    column_map: dict[str, int] = {}
    for field_name, aliases in COLORANTE_ALIASES.items():
        col = _find_column(ws, header_row, aliases)
        if col is not None:
            column_map[field_name] = col

    # Los campos "core" (familia, color, RGB, base, etc.) se buscan solo antes de la
    # primera columna COL_1: el encabezado repite "Y"/"R"/"COSTO" por cada bloque de
    # colorante, y sin este limite el "R" de RGB terminaria resuelto contra el "R"
    # interno del ultimo bloque (COL_4) en vez de la columna real de RGB.
    limit_col = column_map.get("col_1", (ws.max_column or 0) + 1)
    header_cells: dict[str, int] = {}
    for cell in ws[header_row]:
        if cell.column >= limit_col:
            break
        if cell.value is not None:
            header_cells.setdefault(_normalize(cell.value), cell.column)

    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in header_cells:
                column_map[field_name] = header_cells[alias]
                break

    return column_map


def _cell(ws, row: int, col: int | None):
    if col is None:
        return None
    return ws.cell(row=row, column=col).value


def _raw_text(value) -> str | None:
    # Se preserva el texto tal cual viene del Excel (sin strip): se confirmo contra
    # formato_final.txt que colores como "Marfil " conservan el espacio final en el
    # archivo de salida real.
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _dash_as_none(value) -> str | None:
    # TOLERANCIA LUZ y PRIMER usan literalmente "-" para "sin dato" (confirmado:
    # 2312/2312 filas del Excel real). Se normaliza a None sin tocar cualquier otro
    # texto real que pudiera aparecer ahi.
    text = _raw_text(value)
    if text is not None and text.strip() == "-":
        return None
    return text


def read_excel_maestro(
    path: Path,
    linea_metadata: LineaMetadata,
    linea_producto: str | None = None,
) -> IngestResult:
    result = IngestResult()
    linea = linea_producto or Path(path).stem

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = _pick_sheet(wb)

    header_row = _find_header_row(ws)
    column_map = _build_column_map(ws, header_row)

    for field_name in ("familia", "color"):
        if field_name not in column_map:
            result.warnings.append(f"{path.name}: no se encontro la columna obligatoria '{field_name}' en el encabezado")

    qty_columns = {
        cf: (column_map[cf] + QUANTITY_OFFSET) if cf in column_map else None
        for cf in COLORANTE_FIELDS
    }

    consecutive_empty = 0
    row_idx = header_row + 1
    while row_idx <= ws.max_row and consecutive_empty < 5:
        color_raw = _cell(ws, row_idx, column_map.get("color"))
        producto_raw = _cell(ws, row_idx, column_map.get("producto"))

        if (color_raw is None or str(color_raw).strip() == "") and (producto_raw is None or str(producto_raw).strip() == ""):
            consecutive_empty += 1
            row_idx += 1
            continue
        consecutive_empty = 0

        familia_raw = _cell(ws, row_idx, column_map.get("familia"))
        familia_str = _raw_text(familia_raw) or ""

        colorantes: list[Colorante] = []
        for cf in COLORANTE_FIELDS:
            codigo = _cell(ws, row_idx, column_map.get(cf))
            if codigo is None or str(codigo).strip() == "":
                continue
            qty = _cell(ws, row_idx, qty_columns.get(cf))
            try:
                onzas = float(qty) if qty is not None and str(qty).strip() != "" else 0.0
            except (TypeError, ValueError):
                result.warnings.append(f"{path.name} fila {row_idx}: cantidad invalida para {cf}='{qty}'")
                onzas = 0.0
            colorantes.append(Colorante(codigo=str(codigo).strip(), onzas_48=onzas))

        def _int_or_none(field_name: str) -> int | None:
            v = _cell(ws, row_idx, column_map.get(field_name))
            if v is None or str(v).strip() == "":
                return None
            try:
                return int(float(v))
            except (TypeError, ValueError):
                result.warnings.append(f"{path.name} fila {row_idx}: valor no numerico en '{field_name}'='{v}'")
                return None

        oz_base_raw = _cell(ws, row_idx, column_map.get("oz_base"))
        try:
            oz_base = float(oz_base_raw) if oz_base_raw is not None and str(oz_base_raw).strip() != "" else None
        except (TypeError, ValueError):
            result.warnings.append(f"{path.name} fila {row_idx}: Oz Base no numerico '{oz_base_raw}'")
            oz_base = None

        cartilla_raw = _raw_text(_cell(ws, row_idx, column_map.get("cartilla")))
        formato_raw = _raw_text(_cell(ws, row_idx, column_map.get("formato")))

        try:
            formula = FormulaCanonica(
                linea_producto=linea,
                origen_archivo=Path(path).name,
                origen_fila=row_idx,
                familia=familia_str,
                clasificacion=linea_metadata.clasificacion,
                producto=linea_metadata.producto,
                cartilla=linea_metadata.cartilla,
                formato=linea_metadata.formato,
                tolerancia_luz=_dash_as_none(_cell(ws, row_idx, column_map.get("tolerancia_luz"))),
                primer=_dash_as_none(_cell(ws, row_idx, column_map.get("primer"))),
                color=_raw_text(color_raw) or "",
                r=_int_or_none("r"),
                g=_int_or_none("g"),
                b=_int_or_none("b"),
                base=_raw_text(_cell(ws, row_idx, column_map.get("base"))),
                oz_base=oz_base,
                colorantes=colorantes,
                metadata={"cartilla_origen": cartilla_raw, "formato_origen": formato_raw},
            )
            result.formulas.append(formula)
        except ValidationError as exc:
            result.warnings.append(f"{path.name} fila {row_idx}: {exc}")

        row_idx += 1

    return result


def read_batch(input_dir: Path) -> IngestResult:
    combined = IngestResult()
    for path in sorted(Path(input_dir).glob("*.xlsx")):
        if parse_expert_filename(path) is not None:
            # expert_<GRUPO>_<MAQUINA>.xlsx: archivo autodescrito (ya trae
            # Clasificacion/Producto/Cartilla/Formato como columnas propias) que se
            # rutea aparte en el pipeline segun la maquina - no pasa por aca.
            continue
        sidecar = sidecar_path_for(path)
        if not sidecar.exists():
            combined.warnings.append(
                f"{path.name}: falta el archivo de metadata '{sidecar.name}' "
                "(Clasificacion/Producto/Cartilla/Formato) - se omite este archivo"
            )
            continue
        try:
            linea_metadata = load_linea_metadata(sidecar)
        except Exception as exc:  # noqa: BLE001 - se reporta y se continua con el resto del lote
            combined.warnings.append(f"{sidecar.name}: metadata invalida ({exc}) - se omite {path.name}")
            continue

        single = read_excel_maestro(path, linea_metadata)
        combined.formulas.extend(single.formulas)
        combined.warnings.extend(single.warnings)
    return combined
