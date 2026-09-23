from tint_sis.config import AppConfig, load_config, save_config


def test_load_config_sin_archivo_devuelve_defaults(tmp_path):
    cfg = load_config(tmp_path / "no_existe.json")
    assert cfg.enabled_grupos == {"MP14", "MP12", "Tiendas 14", "Tiendas 12"}
    assert cfg.productos_name == "productos_TINT.xlsx"
    assert cfg.expertos == {
        "Experto 1": "Experto_1*.xlsx",
        "Experto 2": "Experto_2*.xls[xm]",
        "Experto 3": "Experto_3*.xlsx",
    }
    assert cfg.filtrados_dirname == "Archivos filtrados"
    softwares = {s.nombre: s for s in cfg.software_defs()}
    assert list(softwares) == ["Santint", "Corob_Tint", "Tinwise_Lab", "Color_Pro3.1.1", "Color_Pro4.8", "Ibicus_Spa"]
    assert softwares["Santint"].tiendas == ("Tiendas 14",)
    assert softwares["Color_Pro3.1.1"].formato == "csv"
    assert softwares["Tinwise_Lab"].experto == "Experto 2"


def test_save_y_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = AppConfig(
        input_dir=tmp_path / "in",
        output_dir=tmp_path / "out",
        db_path=tmp_path / "x.db",
        enabled_grupos={"MP12"},
        delivery_paths={"MP12": r"D:\entrega\mp12"},
        expertos={"Experto 1": "E1*.xlsx", "Experto 2": "E2*.xlsm", "Experto 3": "E3*.xlsx"},
        softwares=[{"nombre": "Santint", "experto": "Experto 3", "tiendas": ["MP12"], "formato": "excel"}],
    )
    save_config(cfg, path)
    back = load_config(path)

    assert back.input_dir == tmp_path / "in"
    assert back.enabled_grupos == {"MP12"}
    assert back.delivery_paths == {"MP12": r"D:\entrega\mp12"}
    assert back.expertos["Experto 1"] == "E1*.xlsx"
    assert [s.nombre for s in back.software_defs()] == ["Santint"]


def test_archivo_parcial_completa_con_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"enabled_grupos": ["MP14"], "expertos": {"Experto 3": "E3*.xlsx"}}', encoding="utf-8")
    cfg = load_config(path)
    assert cfg.enabled_grupos == {"MP14"}
    assert cfg.expertos["Experto 3"] == "E3*.xlsx"
    assert cfg.expertos["Experto 1"] == "Experto_1*.xlsx"  # default
    assert cfg.homologos_master_name == "homologos_TINT.xlsx"


def test_config_viejo_con_expert_glob_se_tolera(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"expert_glob": "xData_DATACOMPLETA*.xlsx", "enabled_grupos": ["MP12"]}', encoding="utf-8")
    cfg = load_config(path)
    assert cfg.enabled_grupos == {"MP12"}
    assert "expert_glob" not in cfg.to_dict()


def test_softwares_invalidos_vuelven_al_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"softwares": [{"nombre": "X", "experto": "Experto 9", "tiendas": ["MP12"], "formato": "excel"}]}',
        encoding="utf-8",
    )
    assert len(load_config(path).software_defs()) == 6
    path.write_text('{"softwares": [{"nombre": "X", "formato": "pdf"}]}', encoding="utf-8")
    assert len(load_config(path).software_defs()) == 6


def test_archivo_corrupto_no_rompe(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ no es json", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.productos_name == "productos_TINT.xlsx"


def test_expertos_habilitados_default_todos_y_roundtrip(tmp_path):
    assert AppConfig().expertos_habilitados == {"Experto 1", "Experto 2", "Experto 3"}

    path = tmp_path / "config.json"
    save_config(AppConfig(expertos_habilitados={"Experto 3"}), path)
    cfg = load_config(path)
    assert cfg.expertos_habilitados == {"Experto 3"}
    assert [s.nombre for s in cfg.softwares_activos()] == ["Santint", "Corob_Tint"]


def test_expertos_habilitados_ignora_labels_desconocidos(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"expertos_habilitados": ["Experto 2", "Experto 9"]}', encoding="utf-8")
    assert load_config(path).expertos_habilitados == {"Experto 2"}
