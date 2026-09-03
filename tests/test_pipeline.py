import openpyxl

from tint_sis.pipeline import run_pipeline


def test_pipeline_end_to_end(tmp_path, sample_excel_with_metadata):
    input_dir = sample_excel_with_metadata.parent
    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"

    summary = run_pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        db_path=db_path,
    )

    assert summary.formulas_leidas == 3
    assert summary.formulas_con_error == 1  # Azul Marino tiene R=300, fuera de rango
    assert summary.formulas_generadas == 2
    assert len(summary.archivos_generados) == 1
    assert summary.archivos_generados[0].exists()
    assert len(summary.archivos_ajuste) == 1
    assert summary.archivos_ajuste[0].exists()

    content = summary.archivos_generados[0].read_bytes().decode("iso-8859-1")
    rows = [r for r in content.split("\r\n") if r]
    assert len(rows) == 3  # header + 2 formulas validas

    assert db_path.exists()


def test_pipeline_skips_excel_without_metadata_sidecar(tmp_path, sample_excel):
    # sample_excel (sin fixture de metadata) no tiene el .json al lado: el pipeline
    # debe omitirlo con una advertencia en vez de romper todo el lote.
    input_dir = sample_excel.parent
    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"

    summary = run_pipeline(input_dir=input_dir, output_dir=output_dir, db_path=db_path)

    assert summary.formulas_leidas == 0
    assert len(summary.archivos_generados) == 0
    assert any("falta el archivo de metadata" in w for w in summary.ingestion_warnings)


def test_pipeline_entrega_csv_y_excel_para_archivo_passthrough(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    path = input_dir / "expert_MP14_Corob4.1.2.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Clasificacion ", "Producto ", "Color ", "R", "Col.1", "1/48 onzas"])
    ws.append(["Latex ", "Ltx. Habitacional Ceresita", "azul celeste", 10, "NE", 3.5])
    wb.save(path)

    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"

    summary = run_pipeline(input_dir=input_dir, output_dir=output_dir, db_path=db_path)

    # No pasa por el flujo clasico FORMULARIO+metadata: no genera ajuste ni .txt.
    assert summary.formulas_leidas == 0
    assert len(summary.archivos_ajuste) == 0
    assert len(summary.archivos_generados) == 0

    assert len(summary.archivos_csv) == 1
    csv_path = summary.archivos_csv[0]
    assert csv_path.name == "expert_MP14_Corob4.1.2.csv"
    assert csv_path.exists()

    assert len(summary.archivos_excel_passthrough) == 1
    excel_path = summary.archivos_excel_passthrough[0]
    assert excel_path.name == "expert_MP14_Corob4.1.2.xlsx"
    assert excel_path.exists()
    assert excel_path.read_bytes() == path.read_bytes()  # copia exacta del original


def test_pipeline_filtra_por_homologos_y_no_pasa_por_flujo_clasico(tmp_path):
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

    # No debe intentar procesarlos como FORMULARIO clasico (sin esto, faltaria
    # expert_test.json / homologos_test.json y saldria una advertencia de
    # "falta el archivo de metadata").
    assert not any("falta el archivo de metadata" in w for w in summary.ingestion_warnings)
    assert summary.formulas_leidas == 0

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
    # Convencion nueva: homologos_TINT.xlsx (maestro fijo) + xData_DATACOMPLETA_*.xlsx
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

    assert not any("falta el archivo de metadata" in w for w in summary.ingestion_warnings)
    assert summary.formulas_leidas == 0

    ready_xlsx = output_dir / "MP12_ready.xlsx"
    ready_csv = output_dir / "MP12_ready.csv"
    assert ready_xlsx in summary.archivos_excel_passthrough
    assert ready_csv in summary.archivos_csv
    assert ready_xlsx.exists() and ready_csv.exists()

    rows = list(openpyxl.load_workbook(ready_xlsx).active.iter_rows(values_only=True))
    assert len(rows) == 2  # encabezado + solo LatHab001 (OleOpacoSipa001 no esta en MP12)
    assert rows[1][0] == "LatHab001"
