from tint_sis.routing import find_homologos_master_pair, find_latest_expert


def test_find_latest_expert_toma_la_fecha_mas_nueva(tmp_path):
    (tmp_path / "Experto_3_03_09_2026.xlsx").touch()
    (tmp_path / "Experto_3_18_09_2026.xlsx").touch()
    (tmp_path / "Experto_3_25_08_2026.xlsx").touch()
    (tmp_path / "Experto_2_30_09_2026.xlsm").touch()

    assert find_latest_expert(tmp_path, "Experto_3*.xlsx") == tmp_path / "Experto_3_18_09_2026.xlsx"
    assert find_latest_expert(tmp_path, "Experto_2*.xls[xm]") == tmp_path / "Experto_2_30_09_2026.xlsm"


def test_find_latest_expert_ignora_temporales_y_xls(tmp_path):
    (tmp_path / "~$Experto_1_03_09_2026.xlsx").touch()
    (tmp_path / "Experto_1.xls").touch()
    assert find_latest_expert(tmp_path, "Experto_1*.xlsx") is None
    assert find_latest_expert(tmp_path / "no_existe", "Experto_1*.xlsx") is None


def test_find_latest_expert_sin_fecha_usa_el_archivo(tmp_path):
    (tmp_path / "Experto_2.xlsm").touch()
    assert find_latest_expert(tmp_path, "Experto_2*.xls[xm]") == tmp_path / "Experto_2.xlsm"


def test_maestro_empareja_homologos_tint_con_xdata(tmp_path):
    (tmp_path / "homologos_TINT.xlsx").touch()
    (tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx").touch()

    pair = find_homologos_master_pair(tmp_path)

    assert pair is not None
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
