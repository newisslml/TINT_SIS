from tint_sis.adapters.coroblab import HEADER, write_coroblab_file
from tint_sis.canonical.models import Colorante, FormulaCanonica


def _formula(**overrides) -> FormulaCanonica:
    data = dict(
        linea_producto="latex_experto",
        origen_archivo="x.xlsx",
        origen_fila=41,
        familia="Latex",
        clasificacion="1.-Latex",
        producto="Latex Experto",
        cartilla="C-100",
        formato="Interior",
        tolerancia_luz="Alta",
        primer="N",
        color="Blanco Tecnoconstrucción",
        r=255,
        g=255,
        b=255,
        base="BT",
        oz_base=100.0,
        colorantes=[Colorante(codigo="AM01", onzas_48=2.5), Colorante(codigo="NG01", onzas_48=0.75)],
    )
    data.update(overrides)
    return FormulaCanonica(**data)


def test_header_has_20_columns():
    assert len(HEADER) == 20


def test_writes_tab_delimited_crlf_iso8859_1(tmp_path):
    out = tmp_path / "linea.txt"
    write_coroblab_file([_formula()], out)

    raw = out.read_bytes()
    text = raw.decode("iso-8859-1")

    lines = text.split("\r\n")
    assert lines[0].split("\t") == HEADER
    assert raw == text.encode("iso-8859-1")

    data_line = lines[1].split("\t")
    assert len(data_line) == 20
    assert data_line[0] == "1.-Latex"
    assert data_line[1] == "Latex Experto"


def test_unused_colorante_slots_show_zero_except_the_last_one(tmp_path):
    # Confirmado contra ajuste_expert.xlsx/formato_final.txt (2312 filas reales):
    # los slots de colorante sin usar muestran "0" en la cantidad, salvo el ultimo
    # (Col. 4), que siempre queda en blanco.
    out = tmp_path / "linea.txt"
    formula = _formula(colorantes=[Colorante(codigo="AM01", onzas_48=2.5)])
    write_coroblab_file([formula], out)

    text = out.read_bytes().decode("iso-8859-1")
    data_line = text.split("\r\n")[1].split("\t")

    assert data_line[12] == "AM01"
    assert data_line[13] == "2.5"
    assert data_line[14] == ""
    assert data_line[15] == "0"
    assert data_line[16] == ""
    assert data_line[17] == "0"
    assert data_line[18] == ""
    assert data_line[19] == ""


def test_number_formatting_matches_reference_file(tmp_path):
    # Formato confirmado contra formato_final.txt: "128" no "128.00", "0.5" no "0.50",
    # "7" no "7.00", "86.5" no "86.50".
    out = tmp_path / "linea.txt"
    formula = _formula(
        oz_base=128.0,
        colorantes=[
            Colorante(codigo="CA", onzas_48=0.5),
            Colorante(codigo="AV", onzas_48=7.0),
            Colorante(codigo="OC", onzas_48=86.5),
        ],
    )
    write_coroblab_file([formula], out)

    text = out.read_bytes().decode("iso-8859-1")
    data_line = text.split("\r\n")[1].split("\t")

    assert data_line[11] == "128"
    assert data_line[13] == "0.5"
    assert data_line[15] == "7"
    assert data_line[17] == "86.5"


def test_accented_characters_roundtrip_iso8859_1(tmp_path):
    out = tmp_path / "linea.txt"
    write_coroblab_file([_formula(color="Rojo Ñuble - TecnoconstrucciÃ³n test Á")], out)

    text = out.read_bytes().decode("iso-8859-1")
    data_line = text.split("\r\n")[1].split("\t")
    assert "Ñuble" in data_line[6]
