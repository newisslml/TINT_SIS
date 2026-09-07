from tint_sis.config import AppConfig, load_config, save_config


def test_load_config_sin_archivo_devuelve_defaults(tmp_path):
    cfg = load_config(tmp_path / "no_existe.json")
    assert cfg.enabled_grupos == {"MP14", "MP12", "Tiendas 14", "Tiendas 12"}
    assert cfg.homologos_master_name == "homologos_TINT.xlsx"
    assert cfg.expert_glob == "xData_DATACOMPLETA*.xlsx"


def test_save_y_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = AppConfig(
        input_dir=tmp_path / "in",
        output_dir=tmp_path / "out",
        db_path=tmp_path / "x.db",
        enabled_grupos={"MP12"},
        delivery_paths={"MP12": r"D:\entrega\mp12"},
    )
    save_config(cfg, path)
    back = load_config(path)

    assert back.input_dir == tmp_path / "in"
    assert back.enabled_grupos == {"MP12"}
    assert back.delivery_paths == {"MP12": r"D:\entrega\mp12"}


def test_archivo_parcial_completa_con_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"enabled_grupos": ["MP14"]}', encoding="utf-8")
    cfg = load_config(path)
    assert cfg.enabled_grupos == {"MP14"}
    assert cfg.homologos_master_name == "homologos_TINT.xlsx"  # default


def test_archivo_corrupto_no_rompe(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ no es json", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.homologos_master_name == "homologos_TINT.xlsx"
