import re
import zipfile

import openpyxl

from libros_prueba import VBA_BYTES, experto_openpyxl, experto_xlsm_a_mano
from tint_sis.adapters.libro_writer import encabezado, reescribir_hoja


def _filas(path, hoja="Formulas"):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [list(r) for r in wb[hoja].iter_rows(values_only=True)]
    finally:
        wb.close()


def test_encabezado_lee_el_valor_guardado_de_las_formulas(tmp_path):
    plantilla = experto_xlsm_a_mano(tmp_path / "E2.xlsm", [["Ltx", "amarillo", 1.5]])
    assert encabezado(plantilla) == ["Producto", "Color", "Qty"]


def test_reescribe_filas_y_conserva_el_resto_del_libro(tmp_path):
    plantilla = experto_xlsm_a_mano(
        tmp_path / "E2.xlsm", [["Ltx", "amarillo", 1.5], ["Oleo", "gris", 2.0], ["Oleo", "negro", 3.0]]
    )
    destino = tmp_path / "salida" / "E2_nuevo.xlsm"
    resultado = reescribir_hoja(
        plantilla,
        destino,
        [["Ltx", " AO", 16.3273125], ["Texturex y Homologos", "amarillo", None], [None, "", 3785]],
    )

    assert resultado.filas == 3
    assert resultado.textos_nuevos == 2  # " AO" y "Texturex y Homologos"; "Ltx" y "amarillo" ya estaban
    assert _filas(destino) == [
        ["Producto", "Color", "Qty"],
        ["Ltx", " AO", 16.3273125],
        ["Texturex y Homologos", "amarillo", None],
        [None, None, 3785],
    ]
    with zipfile.ZipFile(plantilla) as zp, zipfile.ZipFile(destino) as zd:
        assert [i.filename for i in zp.infolist()] == [i.filename for i in zd.infolist()]
        # macros, hoja auxiliar y calcChain (solo apunta a la formula del encabezado) intactos
        for parte in ("xl/vbaProject.bin", "xl/worksheets/sheet2.xml", "xl/calcChain.xml"):
            assert zd.read(parte) == zp.read(parte)
        assert zd.read("xl/vbaProject.bin") == VBA_BYTES
        hoja = zd.read("xl/worksheets/sheet1.xml")
        assert b"<f>IF(1,&quot;Producto&quot;,&quot;x&quot;)</f>" in hoja or b"<f>IF(1,\"Producto\",\"x\")</f>" in hoja
        assert b'<dimension ref="A1:C4"/>' in hoja
        assert b'<autoFilter ref="A1:C4"/>' in hoja
        # el numero toma el estilo de su columna en la primera fila de datos de la plantilla
        assert b'<c r="C2" s="1"><v>16.3273125</v></c>' in hoja
        assert b'<c r="C4" s="1"><v>3785</v></c>' in hoja
        assert b"Formulas!$A$1:$C$4" in zd.read("xl/workbook.xml")
        sst = zd.read("xl/sharedStrings.xml")
        # el espacio adelante del codigo se conserva
        assert b'<t xml:space="preserve"> AO</t>' in sst
        unicos = len(re.findall(rb"<si>", sst))
        assert re.search(rb'uniqueCount="(\d+)"', sst).group(1) == str(unicos).encode()


def test_reutiliza_los_indices_de_textos_existentes(tmp_path):
    plantilla = experto_xlsm_a_mano(tmp_path / "E2.xlsm", [["Látex ", "amarillo", 1]])
    destino = tmp_path / "E2_nuevo.xlsm"
    reescribir_hoja(plantilla, destino, [["Látex ", "amarillo", 1], ["Látex ", "CP-70", 2]])
    assert _filas(destino)[1:] == [["Látex ", "amarillo", 1], ["Látex ", "CP-70", 2]]
    with zipfile.ZipFile(plantilla) as zp, zipfile.ZipFile(destino) as zd:
        antes = zp.read("xl/sharedStrings.xml").count(b"<si>")
        despues = zd.read("xl/sharedStrings.xml")
        assert despues.count(b"<si>") == antes + 1  # solo "CP-70" es nuevo
        # count = referencias: 1 del encabezado (Color) + 4 de las filas nuevas
        assert b'count="5"' in despues


def test_plantilla_sin_shared_strings_escribe_el_texto_en_la_celda(tmp_path):
    plantilla = experto_openpyxl(tmp_path / "E3.xlsx", ["group_code", "product_code"], [["Látex ", "Habitacional"]])
    destino = tmp_path / "E3_nuevo.xlsx"
    reescribir_hoja(plantilla, destino, [["Látex ", "Habitacional"], ["Látex ", "CP-70"]])
    assert _filas(destino) == [["group_code", "product_code"], ["Látex ", "Habitacional"], ["Látex ", "CP-70"]]
    with zipfile.ZipFile(plantilla) as zp, zipfile.ZipFile(destino) as zd:
        assert b'<c r="A3" t="inlineStr"><is><t xml:space="preserve">L' in zd.read("xl/worksheets/sheet1.xml")
        # la hoja IntegrityData no cambia
        assert zd.read("xl/worksheets/sheet2.xml") == zp.read("xl/worksheets/sheet2.xml")


def test_emite_progreso(tmp_path):
    plantilla = experto_openpyxl(tmp_path / "E3.xlsx", ["a"], [["x"]])
    eventos = []
    reescribir_hoja(
        plantilla, tmp_path / "o.xlsx", ([str(i)] for i in range(5)), total=5, on_progress=eventos.append,
        progress_every=2,
    )
    assert {"escritas": 2, "total": 5} in eventos
    assert eventos[-1] == {"guardando": True}
