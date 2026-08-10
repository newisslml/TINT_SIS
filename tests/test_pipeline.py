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
