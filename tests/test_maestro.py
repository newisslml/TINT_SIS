import pytest

from libros_prueba import HEADER_E2_PLANTILLA, HEADER_E3_PLANTILLA, HEADER_MAESTRO
from tint_sis import maestro
from tint_sis.adapters.sheet_filter import FormatoExpertoError


@pytest.mark.parametrize(
    "celda, esperado",
    [
        ("AO-26.5", ("AO", 26.5)),
        (" oc - 3,5 ", ("OC", 3.5)),
        ("BC-117", ("BC", 117.0)),
        ("-0", None),
        ("", None),
        (None, None),
        ("0", None),
    ],
)
def test_parse_colorante(celda, esperado):
    assert maestro.parse_colorante(celda) == esperado


@pytest.mark.parametrize("celda", ["AO26", "AO-", "26.5", "AO-2-6"])
def test_parse_colorante_ilegible(celda):
    with pytest.raises(maestro.ColoranteError):
        maestro.parse_colorante(celda)


def test_galones_por_formato():
    assert maestro.galones("Galon") == 1
    assert maestro.galones("Galon (3.785 Lts.)") == 1
    assert maestro.galones(" tineta 4 GL ") == 4
    assert maestro.equivalencia("Tineta 4 gl") == (4, False)


@pytest.mark.parametrize(
    "formato, galones",
    [
        ("Balde 5 gl", 5),
        ("Tineta 4 galones", 4),
        ("1/4 Galón", 0.25),
        ("Litro", 1 / 3.785),
        ("Envase 3,785 Lts", 1),
    ],
)
def test_galones_por_el_nombre_del_formato(formato, galones):
    g, deducido = maestro.equivalencia(formato)
    assert g == pytest.approx(galones) and deducido


@pytest.mark.parametrize("formato", ["Balde", "Cuarto de galon", "Medio galón", "", None])
def test_formato_sin_equivalencia(formato):
    assert maestro.equivalencia(formato) == (None, False)


def test_a_galon_divide_oz_base_y_colorantes_y_conserva_la_grafia():
    cols = maestro.Columnas.desde_encabezado(HEADER_MAESTRO)
    fila = _fila_maestro(c13=" ve - 44,4 ")
    assert maestro.a_galon(cols, fila) == {3: "Galon", 11: 68.625, 12: "OC-15.7", 13: " ve - 11,1 "}
    # vacias ("-0") y Oz base no numerico quedan igual; un entero queda entero
    fila = _fila_maestro(c11="s/n", c12="AO-32", c13="-0")
    assert maestro.a_galon(cols, fila) == {3: "Galon", 12: "AO-8"}
    # 0.1 / 4 = 0.025 exacto (sin ruido de coma flotante)
    assert maestro.a_galon(cols, _fila_maestro(c11="1", c12="AO-0.1"))[12] == "AO-0.025"
    # ya en galon (o formato desconocido): nada que cambiar
    assert maestro.a_galon(cols, _fila_maestro(c3="Galon (3.785 Lts.)")) == {}
    assert maestro.a_galon(cols, _fila_maestro(c3="Balde")) == {}


def test_columnas_por_encabezado_y_faltantes():
    cols = maestro.Columnas.desde_encabezado(HEADER_MAESTRO)
    assert cols.pos["producto"] == 1
    assert cols.pos["tolerancia"] == 4
    assert cols.colorantes == (12, 13)
    with pytest.raises(FormatoExpertoError, match="formato del maestro"):
        maestro.Columnas.desde_encabezado(["FAMILIA", "PRODUCTO", "Col.1-1/48 onzas"])


def test_plantillas_cuentan_colorantes_y_usan_la_primera_columna_repetida():
    e2 = maestro.plantilla_e2(HEADER_E2_PLANTILLA)
    e3 = maestro.plantilla_e3(HEADER_E3_PLANTILLA)
    assert e2.max_colorantes == 2
    assert e3.max_colorantes == 2
    assert e2.pos["color"] == 3  # E2 repite "Color" despues de R, G, B
    assert e2.faltantes(maestro.CAMPOS_E2) == []
    assert e3.faltantes(maestro.CAMPOS_E3) == []


def _fila_maestro(**cambios):
    fila = ["Texturas", "Texturex y Homologos ", "SW", "Tineta 4 gl", "Batir Tineta", None, "Alamo ",
            "10", "20", "30", "según producto", "274.5", "OC-62.8", "ve-44.4"]
    for i, v in cambios.items():
        fila[int(i[1:])] = v
    return fila


def test_fila_e3_en_galon():
    cols = maestro.Columnas.desde_encabezado(HEADER_MAESTRO)
    tpl = maestro.plantilla_e3(HEADER_E3_PLANTILLA)
    fila = _fila_maestro()
    colorantes = maestro.colorantes_por_galon(cols.celdas_colorante(fila), 4)
    nombres = maestro.NombresProducto(e2="Texturex y Homologos", e3_grupo="Texturas", e3_producto="Texturex")
    out = maestro.fila_e3(cols, fila, nombres, "según producto", colorantes, tpl)
    assert out == [
        "Texturas", "Texturex", "Alamo ", None, None, "Batir Tineta", "según producto", "Galon",
        "USoz/48", 29.574, 48, 0, 10, 20, 30, "OC", 15.7, "VE", 11.1,
    ]


def test_fila_e2_en_cm3_con_espacio_en_el_codigo():
    cols = maestro.Columnas.desde_encabezado(HEADER_MAESTRO)
    tpl = maestro.plantilla_e2(HEADER_E2_PLANTILLA)
    fila = _fila_maestro(c3="Galon", c5="*USAR PRIMER GRIS", c12="AO-26.5", c13=None)
    colorantes = maestro.colorantes_por_galon(cols.celdas_colorante(fila), 1)
    nombres = maestro.NombresProducto(e2="Ltx.Habitacional Ceresita", e3_grupo="Látex ", e3_producto="Habitacional")
    out = maestro.fila_e2(cols, fila, nombres, "Latex ", colorantes, tpl)
    assert out[:8] == ["Latex ", "Ltx.Habitacional Ceresita", "SW", "Alamo ", None, None, "según producto", 3785]
    assert out[8] == " AO"
    assert out[9] == pytest.approx(16.3273125)
    assert out[10:12] == [None, None]
    assert out[12:15] == [10, 20, 30]
    assert out[16:] == ["Batir Tineta", "*USAR PRIMER GRIS"]


def test_numero():
    assert maestro.numero("239") == 239
    assert maestro.numero("274.5") == 274.5
    assert maestro.numero(" ") is None
    assert maestro.numero("s/n") == "s/n"
