from pathlib import Path

from tint_sis.routing import parse_expert_filename


def test_parses_grupo_y_maquina_de_nombre_registrado():
    route = parse_expert_filename(Path("data/input/expert_MP14_Corob4.1.2.xlsx"))
    assert route is not None
    assert route.grupo == "MP14"
    assert route.maquina == "Corob4.1.2"
    assert route.formato_salida == "csv_passthrough"


def test_maquina_no_registrada_devuelve_formato_salida_none():
    route = parse_expert_filename(Path("data/input/expert_MP12_Fluid2.0.xlsx"))
    assert route is not None
    assert route.grupo == "MP12"
    assert route.maquina == "Fluid2.0"
    assert route.formato_salida is None


def test_archivo_sin_convencion_no_matchea():
    assert parse_expert_filename(Path("data/input/expert.xlsx")) is None
    assert parse_expert_filename(Path("data/input/test5.xlsx")) is None


def test_acepta_sufijo_numerado_despues_de_expert():
    route = parse_expert_filename(Path("data/input/expert1_MP14_Corob4.1.2.xlsx"))
    assert route is not None
    assert route.grupo == "MP14"
    assert route.maquina == "Corob4.1.2"
    assert route.formato_salida == "csv_passthrough"
