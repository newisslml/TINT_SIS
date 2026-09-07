from tint_sis.routing import find_homologos_expert_pairs, find_homologos_master_pair


def test_empareja_homologos_con_su_expert_del_mismo_sufijo(tmp_path):
    (tmp_path / "homologos_test.xlsx").touch()
    (tmp_path / "expert_test.xlsx").touch()

    pairs = find_homologos_expert_pairs(tmp_path)

    assert len(pairs) == 1
    assert pairs[0].sufijo == "test"
    assert pairs[0].homologos_path == tmp_path / "homologos_test.xlsx"
    assert pairs[0].expert_path == tmp_path / "expert_test.xlsx"


def test_homologos_sin_expert_con_mismo_sufijo_se_ignora(tmp_path):
    (tmp_path / "homologos_test.xlsx").touch()
    # No hay expert_test.xlsx, solo uno con otro sufijo - no deben emparejarse.
    (tmp_path / "expert_original.xlsx").touch()

    assert find_homologos_expert_pairs(tmp_path) == []


def test_maestro_empareja_homologos_tint_con_xdata(tmp_path):
    (tmp_path / "homologos_TINT.xlsx").touch()
    (tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx").touch()

    pair = find_homologos_master_pair(tmp_path)

    assert pair is not None
    assert pair.sufijo == "TINT"
    assert pair.homologos_path == tmp_path / "homologos_TINT.xlsx"
    assert pair.expert_path == tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx"


def test_maestro_toma_el_experto_de_fecha_mas_nueva(tmp_path):
    (tmp_path / "homologos_TINT.xlsx").touch()
    (tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx").touch()
    (tmp_path / "xData_DATACOMPLETA_18_09_2026.xlsx").touch()
    (tmp_path / "xData_DATACOMPLETA_25_08_2026.xlsx").touch()

    pair = find_homologos_master_pair(tmp_path)

    assert pair is not None
    assert pair.expert_path == tmp_path / "xData_DATACOMPLETA_18_09_2026.xlsx"


def test_maestro_sin_homologos_o_sin_experto_devuelve_none(tmp_path):
    assert find_homologos_master_pair(tmp_path) is None

    (tmp_path / "homologos_TINT.xlsx").touch()
    assert find_homologos_master_pair(tmp_path) is None  # falta el experto

    (tmp_path / "homologos_TINT.xlsx").unlink()
    (tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx").touch()
    assert find_homologos_master_pair(tmp_path) is None  # falta el homologos


def test_homologos_tint_no_lo_agarra_la_convencion_vieja(tmp_path):
    # homologos_TINT.xlsx matchea el glob "homologos_*" pero lo maneja el flujo
    # maestro, no find_homologos_expert_pairs (que buscaria un expert_TINT.xlsx).
    (tmp_path / "homologos_TINT.xlsx").touch()
    (tmp_path / "expert_TINT.xlsx").touch()

    assert find_homologos_expert_pairs(tmp_path) == []
