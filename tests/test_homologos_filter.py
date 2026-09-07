import openpyxl
import pytest

from tint_sis.adapters import homologos_filter
from tint_sis.adapters.homologos_filter import (
    filter_expert_by_ids,
    read_homologos_ids,
    run_homologos_filter,
)

EXPERT_HEADER = ["ID_TINT", "group_code", "product_code", "color_key1", "R"]


@pytest.fixture
def sample_expert(tmp_path):
    path = tmp_path / "expert_idnew.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(EXPERT_HEADER)
    ws.append(["LatHab001", "Latex ", "Habitacional", "azul celeste", 10])
    ws.append(["LatHab002", "Latex ", "Habitacional", "amarillo rey", 249])
    ws.append(["EsmSCereluxe Aquatech001", "Esm. Sinteticos", "Cereluxe Aquatech", "blanco", 255])
    wb.save(path)
    return path


@pytest.fixture
def sample_homologos(tmp_path):
    # Reproduce la estructura real de las hojas de homologos ya pobladas:
    # titulo, tabla de categorias, encabezado con la columna ID_TINT en B,
    # encabezado de seccion, fila de homologo, y debajo una fila por ID_TINT.
    path = tmp_path / "homologos_idnew.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MP12"
    ws.append(["LISTADO PRODUCTOS HOMOLOGOS TWIST MP+ 12"])
    ws.append([])
    ws.append([])
    ws.append(["PRODUCTOS", "ID_TINT", "ID", "CODE", "DESCR", "PATH"])
    ws.append([None, None, 1, "Latex", "Latex", "PROD0001"])
    ws.append(["Latex -  PROD0001", None, "ID,C,5", "CODE,C,34", "DESCR,C,34", "PATH,C,12"])
    ws.append([None, None, 4, "Habitacional Ceresita", "Habitacional Ceresita", "SUBP0004"])
    ws.append([None, "LatHab001", None, "Habitacional Ceresita"])
    ws.append([None, "LatHab002", None, "Habitacional Ceresita"])
    ws.append([])
    ws.append([None, None, 11, "Cereluxe Ceresita (BS)", "Cereluxe Ceresita (BS)", "SUBP0011"])
    ws.append([None, "EsmSCereluxe Aquatech001", None, "Cereluxe Ceresita (BS)"])

    ws2 = wb.create_sheet("MP14")
    ws2.append(["PRODUCTOS", "ID_TINT", "ID", "CODE", "DESCR", "PATH"])
    ws2.append([None, None, 1, "Latex", "Latex", "PROD0001"])
    ws2.append([None, "LatHab001", None, "Habitacional Ceresita"])

    wb.save(path)
    return path


def test_read_homologos_ids_lee_la_columna_id_tint(sample_homologos):
    ids = read_homologos_ids(sample_homologos, "MP12")
    assert ids == {"LatHab001", "LatHab002", "EsmSCereluxe Aquatech001"}


def test_read_homologos_ids_ignora_filas_de_estructura(sample_homologos):
    # Numeros de categoria (col ID), encabezados de seccion ("ID,C,5"), nombres
    # de homologo y el propio encabezado "ID_TINT" no deben colarse al set.
    ids = read_homologos_ids(sample_homologos, "MP12")
    assert 1 not in ids
    assert "ID_TINT" not in ids
    assert "ID,C,5" not in ids
    assert "Habitacional Ceresita" not in ids


def test_read_homologos_ids_acepta_alias_tint_id(tmp_path):
    path = tmp_path / "homologos_alias.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MP12"
    ws.append(["PRODUCTOS", "TINT_ID", "ID", "CODE"])
    ws.append([None, "LatHab001", None, "Habitacional Ceresita"])
    ws.append([None, "LatHab002", None, "Habitacional Ceresita"])
    wb.save(path)

    assert read_homologos_ids(path, "MP12") == {"LatHab001", "LatHab002"}


def test_read_homologos_ids_sin_columna_devuelve_vacio(tmp_path):
    path = tmp_path / "homologos_sincol.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MP12"
    ws.append(["PRODUCTOS", "ID", "CODE", "DESCR"])
    ws.append([None, 4, "Habitacional Ceresita", "Habitacional Ceresita"])
    wb.save(path)

    assert read_homologos_ids(path, "MP12") == set()


def test_filter_expert_by_ids_conserva_solo_las_filas_pedidas(tmp_path, sample_expert):
    out = tmp_path / "out.xlsx"
    written = filter_expert_by_ids(sample_expert, {"LatHab001", "EsmSCereluxe Aquatech001"}, out)

    assert written == 2
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == tuple(EXPERT_HEADER)
    assert rows[1][0] == "LatHab001"
    assert rows[2][0] == "EsmSCereluxe Aquatech001"


def test_filter_expert_by_ids_no_modifica_el_archivo_original(tmp_path, sample_expert):
    original_bytes = sample_expert.read_bytes()
    filter_expert_by_ids(sample_expert, {"LatHab001"}, tmp_path / "out.xlsx")
    assert sample_expert.read_bytes() == original_bytes


def test_filter_expert_by_ids_emite_progreso(tmp_path, sample_expert):
    eventos = []
    written = filter_expert_by_ids(
        sample_expert,
        {"LatHab001"},
        tmp_path / "out.xlsx",
        on_progress=eventos.append,
        progress_every=1,
    )
    assert written == 1
    filas = [e for e in eventos if "leidas" in e]
    assert filas, "deberia emitir al menos un evento de progreso de filas"
    ultimo = filas[-1]
    assert ultimo["leidas"] == 3  # sample_expert tiene 3 filas de datos
    assert ultimo["total"] == 3  # openpyxl declara la dimension -> hay total
    assert ultimo["escritas"] == 1
    # y un evento avisando que arranca el guardado del xlsx (sin hook posible)
    assert any(e.get("guardando") for e in eventos)


def test_filter_expert_by_ids_usa_la_hoja_formulas(tmp_path):
    # El workbook experto real trae hojas auxiliares antes de "Formulas"
    # (p.ej. "ID_new"); se debe leer "Formulas", no la primera hoja.
    path = tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx"
    wb = openpyxl.Workbook()
    decoy = wb.active
    decoy.title = "ID_new"
    decoy.append(["group_code", "Corre", None, "color_key1", None, None, None, "ID"])
    decoy.append(["Latex ", "x", None, "azul", None, None, None, "NO_DEBERIA_SALIR"])
    formulas = wb.create_sheet("Formulas")
    formulas.append(EXPERT_HEADER)
    formulas.append(["LatHab001", "Latex ", "Habitacional", "azul celeste", 10])
    formulas.append(["LatHab002", "Latex ", "Habitacional", "amarillo rey", 249])
    wb.save(path)

    out = tmp_path / "out.xlsx"
    written = filter_expert_by_ids(path, {"LatHab001", "NO_DEBERIA_SALIR"}, out)

    assert written == 1
    rows = list(openpyxl.load_workbook(out).active.iter_rows(values_only=True))
    assert rows[0] == tuple(EXPERT_HEADER)
    assert rows[1][0] == "LatHab001"


def test_filter_expert_by_ids_ubica_la_columna_id_por_encabezado(tmp_path):
    # En "Formulas" el ID no siempre es la primera columna; se ubica por
    # encabezado ("ID" / "ID_TINT"), no por posicion.
    path = tmp_path / "xData_DATACOMPLETA_03_09_2026.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Formulas"
    ws.append(["group_code", "product_code", "ID_TINT", "color_key1"])
    ws.append(["Latex ", "Habitacional", "LatHab001", "azul celeste"])
    ws.append(["Latex ", "Habitacional", "LatHab002", "amarillo rey"])
    wb.save(path)

    out = tmp_path / "out.xlsx"
    written = filter_expert_by_ids(path, {"LatHab002"}, out)

    assert written == 1
    rows = list(openpyxl.load_workbook(out).active.iter_rows(values_only=True))
    assert rows[1][2] == "LatHab002"


def test_filter_expert_by_ids_soporta_celdas_sin_number_format(tmp_path):
    # openpyxl en modo read_only puede devolver number_format=None para celdas
    # nunca formateadas explicitamente (confirmado corriendo contra el archivo
    # experto real) - no debe romper el guardado del xlsx filtrado.
    path = tmp_path / "expert_idnew.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(EXPERT_HEADER)
    ws.append(["LatHab001", "Latex ", "Habitacional", "azul celeste", None])
    wb.save(path)

    out = tmp_path / "out.xlsx"
    written = filter_expert_by_ids(path, {"LatHab001"}, out)
    assert written == 1
    assert out.exists()


def test_run_homologos_filter_genera_xlsx_y_csv_solo_para_grupo_habilitado(
    tmp_path, sample_expert, sample_homologos, monkeypatch
):
    monkeypatch.setattr(homologos_filter, "ENABLED_GRUPOS", {"MP12"})
    output_dir = tmp_path / "output"
    results, warnings = run_homologos_filter(sample_expert, sample_homologos, output_dir)

    assert len(results) == 1
    result = results[0]
    assert result.grupo == "MP12"
    assert result.filas_filtradas == 3
    assert result.xlsx_path == output_dir / "MP12_ready.xlsx"
    assert result.csv_path == output_dir / "MP12_ready.csv"
    assert result.xlsx_path.exists()
    assert result.csv_path.exists()

    # MP14 esta en el archivo de homologos pero no habilitado en este test -
    # debe generar advertencia y no archivo.
    assert any("MP14" in w and "no esta habilitado" in w for w in warnings)
    assert not (output_dir / "MP14_ready.xlsx").exists()


def test_run_homologos_filter_csv_tiene_el_mismo_formato_que_passthrough(
    tmp_path, sample_expert, sample_homologos, monkeypatch
):
    monkeypatch.setattr(homologos_filter, "ENABLED_GRUPOS", {"MP12"})
    output_dir = tmp_path / "output"
    results, _ = run_homologos_filter(sample_expert, sample_homologos, output_dir)

    csv_bytes = results[0].csv_path.read_bytes()
    text = csv_bytes.decode("iso-8859-1")
    assert "\r\n" in text
    lines = [line for line in text.split("\r\n") if line]
    assert lines[0] == ",".join(EXPERT_HEADER)
    assert lines[1].startswith("LatHab001,")
