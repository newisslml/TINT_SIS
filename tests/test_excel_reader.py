from tint_sis.ingestion.excel_reader import read_excel_maestro


def test_reads_all_data_rows(sample_excel, linea_metadata):
    result = read_excel_maestro(sample_excel, linea_metadata, linea_producto="latex_experto")
    assert len(result.formulas) == 3


def test_metadata_fields_are_stamped_from_linea_metadata_not_raw_excel(sample_excel, linea_metadata):
    # Clasificacion/Producto/Cartilla/Formato NO se calculan del Excel: son un "sello"
    # fijo por linea de producto (confirmado contra expert.xlsx / ajuste_expert.xlsx:
    # la columna cruda CARTILLA cambia varias veces en el archivo real pero la salida
    # limpia usa siempre los mismos 4 valores).
    result = read_excel_maestro(sample_excel, linea_metadata)

    for formula in result.formulas:
        assert formula.clasificacion == linea_metadata.clasificacion
        assert formula.producto == linea_metadata.producto
        assert formula.cartilla == linea_metadata.cartilla
        assert formula.formato == linea_metadata.formato


def test_raw_cartilla_and_formato_kept_as_audit_metadata(sample_excel, linea_metadata):
    result = read_excel_maestro(sample_excel, linea_metadata)
    formula = result.formulas[0]
    assert formula.metadata["cartilla_origen"] == "L. Experto "
    assert formula.metadata["formato_origen"] == "Galon"


def test_dash_becomes_none_for_tolerancia_luz_and_primer(sample_excel, linea_metadata):
    result = read_excel_maestro(sample_excel, linea_metadata)
    for formula in result.formulas:
        assert formula.tolerancia_luz is None
        assert formula.primer is None


def test_handles_variable_colorant_count(sample_excel, linea_metadata):
    result = read_excel_maestro(sample_excel, linea_metadata)
    by_color = {f.color: f for f in result.formulas}

    assert len(by_color["Blanco Tecnoconstrucción "].colorantes) == 2
    assert len(by_color["Rojo Ñuble"].colorantes) == 1
    assert len(by_color["Azul Marino"].colorantes) == 3


def test_colorante_quantity_uses_the_correct_column_offset(sample_excel, linea_metadata):
    # Regresion: la cantidad real esta en COL_n + 3 ("1/48 onzas"), no en COL_n + 1.
    result = read_excel_maestro(sample_excel, linea_metadata)
    by_color = {f.color: f for f in result.formulas}

    rojo = by_color["Rojo Ñuble"]
    assert rojo.colorantes[0].codigo == "RO02"
    assert rojo.colorantes[0].onzas_48 == 4.0


def test_rgb_column_is_not_confused_with_per_colorante_r_column(sample_excel, linea_metadata):
    # Regresion: el encabezado "R" aparece 5 veces (RGB + 1 por cada bloque de
    # colorante); sin acotar la busqueda a las columnas antes de COL_1, el R de RGB
    # terminaba resuelto contra el R interno del ultimo bloque de colorante.
    result = read_excel_maestro(sample_excel, linea_metadata)
    by_color = {f.color: f for f in result.formulas}

    rojo = by_color["Rojo Ñuble"]
    assert (rojo.r, rojo.g, rojo.b) == (200, 10, 10)


def test_preserves_accented_characters_and_trailing_whitespace(sample_excel, linea_metadata):
    # Confirmado contra formato_final.txt: colores como "Marfil " conservan el
    # espacio final tal cual viene del Excel; no se debe hacer .strip().
    result = read_excel_maestro(sample_excel, linea_metadata)
    colors = {f.color for f in result.formulas}

    assert "Blanco Tecnoconstrucción " in colors
    assert "Rojo Ñuble" in colors


def test_origen_metadata_is_captured(sample_excel, linea_metadata):
    result = read_excel_maestro(sample_excel, linea_metadata, linea_producto="latex_experto")

    assert all(f.linea_producto == "latex_experto" for f in result.formulas)
    assert all(f.origen_archivo == sample_excel.name for f in result.formulas)
    assert result.formulas[0].origen_fila == 40
