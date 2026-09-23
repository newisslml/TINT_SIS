import openpyxl

from tint_sis.config import AppConfig
from tint_sis.preview import preview_batch


def _cfg(tmp_path, **kw):
    inp = tmp_path / "input"
    inp.mkdir()
    return AppConfig(input_dir=inp, output_dir=tmp_path / "out", db_path=tmp_path / "x.db", **kw)


def _xlsx(path, sheet="Hoja"):
    wb = openpyxl.Workbook()
    wb.active.title = sheet
    wb.active.append(["a"])
    wb.save(path)


def _completa(cfg):
    _xlsx(cfg.input_dir / "productos_TINT.xlsx", "Productos")
    _xlsx(cfg.input_dir / "Experto_1_07_09_2026.xlsx")
    _xlsx(cfg.input_dir / "Experto_2_15_09_2026.xlsm", "Formulas")
    _xlsx(cfg.input_dir / "Experto_3_22_09_2026.xlsx", "Formulas")


def test_preview_carpeta_vacia_no_puede_ejecutar(tmp_path):
    cfg = _cfg(tmp_path)
    prev = preview_batch(cfg)
    assert prev.archivos == []
    assert prev.puede_ejecutar is False
    assert any("tabla de productos" in b for b in prev.bloqueantes)
    assert any("ningun archivo experto" in b for b in prev.bloqueantes)


def test_preview_clasifica_tabla_expertos_y_basura(tmp_path):
    cfg = _cfg(tmp_path)
    _completa(cfg)
    _xlsx(cfg.input_dir / "lista_precios.xlsx")
    _xlsx(cfg.input_dir / "homologos_TINT.xlsx", "MP12")

    prev = preview_batch(cfg)
    por_archivo = {a.archivo: a for a in prev.archivos}

    assert prev.puede_ejecutar is True
    assert prev.productos_activo == "productos_TINT.xlsx"
    assert por_archivo["productos_TINT.xlsx"].flujo == "Tabla de productos"
    e3 = por_archivo["Experto_3_22_09_2026.xlsx"]
    assert (e3.estado, e3.flujo, e3.software) == ("ok", "Experto 3", "Santint, Corob_Tint")
    assert por_archivo["Experto_2_15_09_2026.xlsm"].software == "Tinwise_Lab"
    assert por_archivo["homologos_TINT.xlsx"].estado == "no-habilitado"
    assert por_archivo["lista_precios.xlsx"].estado == "error"
    assert [(e.label, e.estado) for e in prev.expertos] == [
        ("Experto 1", "ok"),
        ("Experto 2", "ok"),
        ("Experto 3", "ok"),
    ]
    assert prev.advertencias == []


def test_preview_experto_viejo_se_ignora_y_el_nuevo_va_primero(tmp_path):
    cfg = _cfg(tmp_path)
    _completa(cfg)
    _xlsx(cfg.input_dir / "Experto_3_25_08_2026.xlsx", "Formulas")

    prev = preview_batch(cfg)
    estados = {a.archivo: a.estado for a in prev.archivos}
    assert estados["Experto_3_22_09_2026.xlsx"] == "ok"
    assert estados["Experto_3_25_08_2026.xlsx"] == "no-habilitado"
    orden = [a.archivo for a in prev.archivos if a.archivo.startswith("Experto_3")]
    assert orden == ["Experto_3_22_09_2026.xlsx", "Experto_3_25_08_2026.xlsx"]


def test_preview_experto_1_en_xls_es_error_y_se_avisa(tmp_path):
    cfg = _cfg(tmp_path)
    _completa(cfg)
    (cfg.input_dir / "Experto_1_07_09_2026.xlsx").unlink()
    (cfg.input_dir / "Experto_1.xls").write_bytes(b"viejo")

    prev = preview_batch(cfg)
    xls = next(a for a in prev.archivos if a.archivo == "Experto_1.xls")
    assert xls.estado == "error" and ".xlsx" in xls.detalle
    assert prev.puede_ejecutar is True  # los otros expertos alcanzan para correr
    assert any("Experto 1" in a and "Color_Pro3.1.1" in a for a in prev.advertencias)
    assert next(e for e in prev.expertos if e.label == "Experto 1").estado == "falta"


def test_preview_sin_tiendas_para_un_experto_no_lo_pide(tmp_path):
    cfg = _cfg(tmp_path, enabled_grupos={"Tiendas 12"})
    _completa(cfg)
    prev = preview_batch(cfg)
    # con solo Tiendas 12, Experto 2 (Tinwise_Lab, solo Tiendas 14) no se usa
    assert [e.label for e in prev.expertos] == ["Experto 1", "Experto 3"]


def test_preview_ignora_temporales_de_excel(tmp_path):
    cfg = _cfg(tmp_path)
    _completa(cfg)
    (cfg.input_dir / "~$Experto_3_22_09_2026.xlsx").write_bytes(b"lock")

    prev = preview_batch(cfg)
    assert all(not a.archivo.startswith("~$") for a in prev.archivos)


def test_preview_experto_desactivado(tmp_path):
    cfg = _cfg(tmp_path, expertos_habilitados={"Experto 2", "Experto 3"})
    _completa(cfg)
    (cfg.input_dir / "Experto_1_07_09_2026.xlsx").unlink()  # desactivado: que falte no importa

    prev = preview_batch(cfg)
    e1 = next(e for e in prev.expertos if e.label == "Experto 1")
    assert e1.estado == "desactivado"
    assert prev.advertencias == []
    assert prev.puede_ejecutar is True


def test_preview_archivo_de_experto_desactivado_se_omite(tmp_path):
    cfg = _cfg(tmp_path, expertos_habilitados={"Experto 3"})
    _completa(cfg)
    prev = preview_batch(cfg)
    e2 = next(a for a in prev.archivos if a.archivo == "Experto_2_15_09_2026.xlsm")
    assert (e2.estado, e2.detalle) == ("desactivado", "Experto desactivado en Configuracion")


def test_preview_todos_los_expertos_desactivados_bloquea(tmp_path):
    cfg = _cfg(tmp_path, expertos_habilitados=set())
    _completa(cfg)
    prev = preview_batch(cfg)
    assert prev.puede_ejecutar is False
    assert any("ningun experto habilitado" in b for b in prev.bloqueantes)


def test_preview_detalle_por_software_para_el_resumen(tmp_path):
    cfg = _cfg(tmp_path, enabled_grupos={"MP14", "Tiendas 14"})
    _completa(cfg)
    prev = preview_batch(cfg)
    e1 = next(e for e in prev.expertos if e.label == "Experto 1")
    assert e1.detalle == [
        {"nombre": "Color_Pro3.1.1", "tiendas": ["Tiendas 14", "MP14"], "formato": "csv"},
        {"nombre": "Color_Pro4.8", "tiendas": ["Tiendas 14"], "formato": "excel"},
        {"nombre": "Ibicus_Spa", "tiendas": ["Tiendas 14"], "formato": "excel"},
    ]
    assert prev.salida == str(cfg.output_dir / "Archivos filtrados")
