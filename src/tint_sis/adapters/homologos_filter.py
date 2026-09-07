from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from openpyxl.cell import WriteOnlyCell

# Firma del callback de progreso: recibe un dict {fase, item, indice, total, mensaje}.
ProgressCallback = Callable[[dict], None]


def _emit(cb: ProgressCallback | None, **event: object) -> None:
    if cb is not None:
        cb(event)

from tint_sis.adapters.passthrough_csv import write_passthrough_csv

# Los grupos/tiendas se habilitan a mano una vez confirmado que su hoja en el
# archivo de homologos y su cruce contra el experto quedaron completos (mismo
# criterio cauteloso que MACHINE_OUTPUT_FORMATS en routing.py: no se adivina).
ENABLED_GRUPOS = {"MP14", "MP12", "Tiendas 14", "Tiendas 12"}

# El ID de cada formula ("ID_TINT") es ahora un codigo alfanumerico libre
# (LatHab001, EsmSCereluxe Aquatech001, TexSipalinahidr4233, ...) y ya no el
# viejo formato TINT###. Las hojas de homologos traen una columna dedicada con
# ese encabezado y una fila por ID debajo de cada homologo, asi que se lee por
# encabezado en vez de por patron. Se acepta el alias historico "TINT_ID".
# Ojo: en las hojas de homologos hay ademas una columna "ID" (numeros de
# categoria) que NO es esta, por eso el bare "id" no entra aca.
ID_HEADER_ALIASES = {"id_tint", "tint_id"}

# En el archivo experto (xData_DATACOMPLETA_*.xlsx) la tabla de formulas esta en
# la hoja "Formulas" (el workbook trae ademas hojas auxiliares como "ID_new" que
# no sirven de experto). Si esa hoja no existe se usa la primera. Ahi la columna
# del ID se llama "ID" o "ID_TINT" y no siempre es la primera, asi que se ubica
# por encabezado.
EXPERT_SHEET_NAME = "Formulas"
EXPERT_ID_HEADERS = {"id", "id_tint", "tint_id"}


def _pick_expert_sheet(wb) -> tuple[object, str]:
    for name in wb.sheetnames:
        if name.strip().lower() == EXPERT_SHEET_NAME.lower():
            return wb[name], name
    first = wb.sheetnames[0]
    return wb[first], first


def _find_expert_id_column(header: list) -> int:
    for idx, value in enumerate(header):
        if isinstance(value, str) and value.strip().lower() in EXPERT_ID_HEADERS:
            return idx
    return 0


def read_homologos_ids(path: Path, grupo: str) -> set[str]:
    """Devuelve el set de ID_TINT presentes en la hoja `grupo` del archivo de
    homologos. Ubica la columna por su encabezado ("ID_TINT" / "TINT_ID") y junta
    todos los valores de texto no vacios que aparecen debajo; los renglones de
    estructura (titulo, categorias, encabezados de seccion, filas de homologo)
    dejan esa celda vacia, asi que no se cuelan. Si la hoja no trae esa columna,
    devuelve un set vacio."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[grupo]
        rows = ws.iter_rows(values_only=True)

        id_col: int | None = None
        for row in rows:
            for idx, value in enumerate(row):
                if isinstance(value, str) and value.strip().lower() in ID_HEADER_ALIASES:
                    id_col = idx
                    break
            if id_col is not None:
                break
        if id_col is None:
            return set()

        ids: set[str] = set()
        for row in rows:  # el generador ya quedo posicionado despues del encabezado
            if id_col >= len(row):
                continue
            value = row[id_col]
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value and value.lower() not in ID_HEADER_ALIASES:
                ids.add(value)
        return ids
    finally:
        wb.close()


def filter_expert_by_ids(
    expert_path: Path,
    ids: set[str],
    output_xlsx_path: Path,
    *,
    on_progress: ProgressCallback | None = None,
    progress_every: int = 2000,
) -> int:
    """Copia de la hoja "Formulas" de expert_path solo las filas cuyo ID_TINT
    esta en `ids`, preservando el number_format original de cada celda (lo
    necesita write_passthrough_csv despues para formatear fechas/decimales igual
    que en el resto del flujo). No modifica expert_path, solo lo lee.

    Devuelve la cantidad de filas de datos escritas (sin contar encabezado).

    `on_progress`, si se pasa, recibe {leidas, total, escritas} cada
    `progress_every` filas del experto (para barra de progreso fina). `total`
    puede ser None si el .xlsx no trae la dimension declarada.
    """
    output_xlsx_path = Path(output_xlsx_path)
    output_xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    wb_in = openpyxl.load_workbook(expert_path, read_only=True, data_only=True)
    ws_in, sheet_name = _pick_expert_sheet(wb_in)
    # ws.max_row sale de la dimension declarada en el XML (instantaneo); incluye
    # el encabezado. Si el archivo no la trae, queda None y el progreso va sin %.
    total_filas = ws_in.max_row
    total_datos = total_filas - 1 if isinstance(total_filas, int) and total_filas > 0 else None
    rows_iter = ws_in.iter_rows()

    header = [c.value for c in next(rows_iter)]
    id_idx = _find_expert_id_column(header)

    wb_out = openpyxl.Workbook(write_only=True)
    ws_out = wb_out.create_sheet(sheet_name)
    ws_out.append(header)

    written = 0
    leidas = 0
    for row in rows_iter:
        leidas += 1
        id_value = row[id_idx].value if id_idx < len(row) else None
        if id_value is not None and str(id_value).strip() in ids:
            written += 1
            out_row = []
            for cell in row:
                out_cell = WriteOnlyCell(ws_out, value=cell.value)
                # cell.number_format puede volver None para celdas nunca formateadas
                # explicitamente en el origen; "General" es el default real de Excel.
                out_cell.number_format = cell.number_format or "General"
                out_row.append(out_cell)
            ws_out.append(out_row)
        if on_progress is not None and leidas % progress_every == 0:
            on_progress({"leidas": leidas, "total": total_datos, "escritas": written})

    if on_progress is not None:
        on_progress({"leidas": leidas, "total": total_datos or leidas, "escritas": written})
        # el .save() de openpyxl (write_only + number_format por celda) es lento y
        # sin hook posible; se avisa aparte para que la UI muestre la etapa.
        on_progress({"guardando": True, "escritas": written})

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
    *,
    enabled_grupos: set[str] | None = None,
    on_progress: ProgressCallback | None = None,
) -> tuple[list[HomologosFilterResult], list[str]]:
    """Por cada hoja (grupo/tienda) del archivo de homologos que este habilitada
    en `enabled_grupos` (default: ENABLED_GRUPOS), filtra expert_path por los IDs
    de esa hoja y genera <grupo>_ready.xlsx + <grupo>_ready.csv en output_dir.
    Ninguno de los dos archivos de entrada se modifica, solo se leen como
    referencia. `on_progress`, si se pasa, recibe eventos por tienda."""
    output_dir = Path(output_dir)
    enabled = enabled_grupos if enabled_grupos is not None else ENABLED_GRUPOS
    results: list[HomologosFilterResult] = []
    warnings: list[str] = []

    wb_h = openpyxl.load_workbook(homologos_path, read_only=True, data_only=True)
    sheet_names = list(wb_h.sheetnames)
    wb_h.close()

    a_procesar = [g for g in sheet_names if g in enabled]
    _emit(on_progress, fase="inicio", total=len(a_procesar), mensaje="Filtro por homologos")

    for grupo in sheet_names:
        if grupo not in enabled:
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
                f"{homologos_path.name}: hoja '{grupo}' no tiene una columna "
                "'ID_TINT' con IDs - se omite"
            )
            continue

        xlsx_path = output_dir / f"{grupo}_ready.xlsx"
        csv_path = output_dir / f"{grupo}_ready.csv"

        # El cruce contra el experto completo (~180k filas) tarda varios minutos
        # y sin este aviso la terminal queda en silencio todo ese tiempo, dando
        # la falsa impresion de que el proceso se colgo.
        print(f"Filtrando Data... ({grupo})")
        indice = len(results) + 1
        _emit(
            on_progress,
            fase="tienda_inicio",
            item=grupo,
            indice=indice,
            total=len(a_procesar),
            mensaje=f"Filtrando {grupo} contra el experto ({len(ids)} IDs)",
        )

        def _relay(etapa: str, _grupo=grupo, _indice=indice) -> ProgressCallback:
            def cb(ev: dict) -> None:
                _emit(
                    on_progress,
                    fase="tienda_progreso",
                    item=_grupo,
                    indice=_indice,
                    total=len(a_procesar),
                    etapa="guardar_xlsx" if ev.get("guardando") else etapa,  # filtrar|guardar_xlsx|csv
                    leidas=ev.get("leidas"),
                    sub_total=ev.get("total"),
                )

            return cb

        filas = filter_expert_by_ids(
            expert_path, ids, xlsx_path, on_progress=_relay("filtrar") if on_progress else None
        )
        write_passthrough_csv(
            xlsx_path,
            csv_path,
            on_progress=_relay("csv") if on_progress else None,
            total_hint=filas,
        )

        results.append(
            HomologosFilterResult(
                grupo=grupo,
                filas_filtradas=filas,
                xlsx_path=xlsx_path,
                csv_path=csv_path,
            )
        )
        _emit(
            on_progress,
            fase="tienda_ok",
            item=grupo,
            indice=indice,
            total=len(a_procesar),
            filas=filas,
            mensaje=f"{grupo}: {filas} filas",
        )

    return results, warnings
