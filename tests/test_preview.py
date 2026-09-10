import openpyxl

from tint_sis.config import AppConfig
from tint_sis.preview import preview_batch


def _cfg(tmp_path):
    inp = tmp_path / "input"
    inp.mkdir()
    return AppConfig(input_dir=inp, output_dir=tmp_path / "out", db_path=tmp_path / "x.db")


def _xlsx(path, sheet="Hoja"):
    wb = openpyxl.Workbook()
    wb.active.title = sheet
    wb.active.append(["a"])
    wb.save(path)


def test_preview_carpeta_vacia_no_puede_ejecutar(tmp_path):
    cfg = _cfg(tmp_path)
    prev = preview_batch(cfg)
    assert prev.archivos == []
    assert prev.puede_ejecutar is False
    assert any("homologos" in b.lower() for b in prev.bloqueantes)


def test_preview_clasifica_maestro_experto_y_basura(tmp_path):
    cfg = _cfg(tmp_path)
    _xlsx(cfg.input_dir / "homologos_TINT.xlsx", "MP12")
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_03_09_2026.xlsx", "Formulas")
    _xlsx(cfg.input_dir / "lista_precios.xlsx")

    prev = preview_batch(cfg)
    estados = {a.archivo: a.estado for a in prev.archivos}

    assert estados["homologos_TINT.xlsx"] == "ok"
    assert estados["xData_DATACOMPLETA_03_09_2026.xlsx"] == "ok"
    assert estados["lista_precios.xlsx"] == "error"
    assert prev.puede_ejecutar is True
    assert prev.experto_activo == "xData_DATACOMPLETA_03_09_2026.xlsx"


def test_preview_experto_viejo_queda_no_habilitado(tmp_path):
    cfg = _cfg(tmp_path)
    _xlsx(cfg.input_dir / "homologos_TINT.xlsx", "MP12")
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_03_09_2026.xlsx", "Formulas")
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_18_09_2026.xlsx", "Formulas")

    prev = preview_batch(cfg)
    estados = {a.archivo: a.estado for a in prev.archivos}

    assert prev.experto_activo == "xData_DATACOMPLETA_18_09_2026.xlsx"
    assert estados["xData_DATACOMPLETA_18_09_2026.xlsx"] == "ok"
    assert estados["xData_DATACOMPLETA_03_09_2026.xlsx"] == "no-habilitado"


def test_preview_ordena_expertos_por_fecha_mas_nuevo_arriba(tmp_path):
    cfg = _cfg(tmp_path)
    _xlsx(cfg.input_dir / "homologos_TINT.xlsx", "MP12")
    # A proposito fuera de orden alfabetico/de creacion: el mas nuevo (18/09) debe
    # listarse primero, luego 03/09, luego el mas viejo (25/08).
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_03_09_2026.xlsx", "Formulas")
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_25_08_2026.xlsx", "Formulas")
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_18_09_2026.xlsx", "Formulas")

    prev = preview_batch(cfg)
    orden_expertos = [a.archivo for a in prev.archivos if a.archivo.startswith("xData_")]

    assert orden_expertos == [
        "xData_DATACOMPLETA_18_09_2026.xlsx",
        "xData_DATACOMPLETA_03_09_2026.xlsx",
        "xData_DATACOMPLETA_25_08_2026.xlsx",
    ]


def test_preview_ignora_temporales_de_excel(tmp_path):
    cfg = _cfg(tmp_path)
    _xlsx(cfg.input_dir / "homologos_TINT.xlsx", "MP12")
    _xlsx(cfg.input_dir / "xData_DATACOMPLETA_03_09_2026.xlsx", "Formulas")
    (cfg.input_dir / "~$xData_DATACOMPLETA_03_09_2026.xlsx").write_bytes(b"lock")

    prev = preview_batch(cfg)
    assert all(not a.archivo.startswith("~$") for a in prev.archivos)
