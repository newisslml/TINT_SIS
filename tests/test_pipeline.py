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
