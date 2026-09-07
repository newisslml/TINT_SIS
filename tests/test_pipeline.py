import openpyxl

from tint_sis.pipeline import run_pipeline


def test_pipeline_filtra_por_homologos_convencion_de_sufijo(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    expert_path = input_dir / "expert_test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Clasificacion ", "Producto ", "Color ", "R"])
    ws.append(["TINT1", "Latex ", "Ltx. Habitacional Ceresita", "azul celeste", 10])
    ws.append(["TINT2", "Oleos", "Oleo Sintetico Constructor", "blanco", 255])
    wb.save(expert_path)

    homologos_path = input_dir / "homologos_test.xlsx"
    wb_h = openpyxl.Workbook()
    ws_h = wb_h.active
    ws_h.title = "MP12"
    ws_h.append(["PRODUCTOS", "TINT_ID", "ID", "CODE", "DESCR", "PATH"])
    ws_h.append([None, "TINT1", None, "Habitacional Ceresita"])
    wb_h.save(homologos_path)

    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"

    summary = run_pipeline(input_dir=input_dir, output_dir=output_dir, db_path=db_path)

    ready_xlsx = output_dir / "MP12_ready.xlsx"
    ready_csv = output_dir / "MP12_ready.csv"
    assert ready_xlsx in summary.archivos_excel_passthrough
    assert ready_csv in summary.archivos_csv
    assert ready_xlsx.exists()
    assert ready_csv.exists()

    wb_out = openpyxl.load_workbook(ready_xlsx)
    rows = list(wb_out.active.iter_rows(values_only=True))
    assert len(rows) == 2  # encabezado + solo TINT1 (TINT2 no esta en homologos MP12)
    assert rows[1][0] == "TINT1"


def test_pipeline_filtra_por_homologos_maestro_fijo(tmp_path):
    # Convencion real: homologos_TINT.xlsx (maestro fijo) + xData_DATACOMPLETA_*.xlsx
    # (experto con fecha en el nombre). Se cruza ID_TINT contra la hoja "Formulas".
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    expert_path = input_dir / "xData_DATACOMPLETA_03_09_2026.xlsx"
    wb = openpyxl.Workbook()
    aux = wb.active
    aux.title = "ID_new"
    aux.append(["group_code", "Corre", "ID"])
    formulas = wb.create_sheet("Formulas")
    formulas.append(["ID", "group_code", "product_code", "color_key1", "R"])
    formulas.append(["LatHab001", "Latex ", "Habitacional", "azul celeste", 10])
    formulas.append(["OleOpacoSipa001", "Oleos", "OpacoSipa", "blanco", 255])
    wb.save(expert_path)

    homologos_path = input_dir / "homologos_TINT.xlsx"
    wb_h = openpyxl.Workbook()
    ws_h = wb_h.active
    ws_h.title = "MP12"
    ws_h.append(["PRODUCTOS", "ID_TINT", "ID", "CODE", "DESCR", "PATH"])
    ws_h.append([None, None, 4, "Habitacional Ceresita", "Habitacional Ceresita", "SUBP0004"])
    ws_h.append([None, "LatHab001", None, "Habitacional Ceresita"])
    wb_h.save(homologos_path)

    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"

    summary = run_pipeline(input_dir=input_dir, output_dir=output_dir, db_path=db_path)

    ready_xlsx = output_dir / "MP12_ready.xlsx"
    ready_csv = output_dir / "MP12_ready.csv"
    assert ready_xlsx in summary.archivos_excel_passthrough
    assert ready_csv in summary.archivos_csv
    assert ready_xlsx.exists() and ready_csv.exists()

    rows = list(openpyxl.load_workbook(ready_xlsx).active.iter_rows(values_only=True))
    assert len(rows) == 2  # encabezado + solo LatHab001 (OleOpacoSipa001 no esta en MP12)
    assert rows[1][0] == "LatHab001"


def test_pipeline_sin_archivos_de_homologos_no_genera_nada(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"

    summary = run_pipeline(input_dir=input_dir, output_dir=output_dir, db_path=db_path)

    assert summary.archivos_csv == []
    assert summary.archivos_excel_passthrough == []
    assert summary.ingestion_warnings == []
