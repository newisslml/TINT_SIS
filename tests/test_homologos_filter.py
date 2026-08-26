import openpyxl
import pytest

from tint_sis.adapters.homologos_filter import (
    filter_expert_by_ids,
    read_homologos_ids,
    run_homologos_filter,
)

EXPERT_HEADER = ["ID", "Clasificacion ", "Producto ", "Color ", "R"]


@pytest.fixture
def sample_expert(tmp_path):
    path = tmp_path / "expert_test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(EXPERT_HEADER)
    ws.append(["TINT1", "Latex ", "Ltx. Habitacional Ceresita", "azul celeste", 10])
    ws.append(["TINT2", "Latex ", "Ltx. Habitacional Ceresita", "amarillo rey", 249])
    ws.append(["TINT3", "Oleos", "Oleo Sintetico Constructor", "blanco", 255])
    wb.save(path)
    return path


@pytest.fixture
def sample_homologos(tmp_path):
    # Reproduce la estructura real: filas de encabezado/categoria intercaladas
    # con los IDs en una columna que no es la primera.
    path = tmp_path / "homologos_test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MP12"
    ws.append(["LISTADO PRODUCTOS HOMOLOGOS TWIST MP+ 12"])
    ws.append(["PRODUCTOS", "TINT_ID", "ID", "CODE", "DESCR", "PATH"])
    ws.append([None, None, 1, "Latex", "Latex", "PROD0001"])
    ws.append([None, "TINT1", None, "Habitacional Ceresita"])
    ws.append([None, "TINT3", None, "Habitacional Ceresita"])  # solo TINT1 y TINT3, no TINT2

    ws2 = wb.create_sheet("MP14")
    ws2.append(["PRODUCTOS", "ID", "CODE", "DESCR", "PATH"])
    ws2.append([None, 1, "Latex", "Latex", "PROD0001"])

    wb.save(path)
    return path


def test_read_homologos_ids_encuentra_ids_en_columna_variable(sample_homologos):
    ids = read_homologos_ids(sample_homologos, "MP12")
    assert ids == {"TINT1", "TINT3"}


def test_read_homologos_ids_ignora_filas_de_categoria(sample_homologos):
    # La fila de categoria tiene un "1" (int) en columna ID, no debe colarse
    # como si fuera un TINT.
    ids = read_homologos_ids(sample_homologos, "MP12")
    assert 1 not in ids
    assert "1" not in ids


def test_filter_expert_by_ids_conserva_solo_las_filas_pedidas(tmp_path, sample_expert):
    out = tmp_path / "out.xlsx"
    written = filter_expert_by_ids(sample_expert, {"TINT1", "TINT3"}, out)

    assert written == 2
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == tuple(EXPERT_HEADER)
    assert rows[1][0] == "TINT1"
    assert rows[2][0] == "TINT3"


def test_filter_expert_by_ids_no_modifica_el_archivo_original(tmp_path, sample_expert):
    original_bytes = sample_expert.read_bytes()
    filter_expert_by_ids(sample_expert, {"TINT1"}, tmp_path / "out.xlsx")
    assert sample_expert.read_bytes() == original_bytes


def test_filter_expert_by_ids_soporta_celdas_sin_number_format(tmp_path):
    # openpyxl en modo read_only puede devolver number_format=None para celdas
    # nunca formateadas explicitamente (confirmado corriendo contra el archivo
    # experto real) - no debe romper el guardado del xlsx filtrado.
    path = tmp_path / "expert_test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(EXPERT_HEADER)
    ws.append(["TINT1", "Latex ", "Ltx. Habitacional Ceresita", "azul celeste", None])
    wb.save(path)

    out = tmp_path / "out.xlsx"
    written = filter_expert_by_ids(path, {"TINT1"}, out)
    assert written == 1
    assert out.exists()


def test_run_homologos_filter_genera_xlsx_y_csv_solo_para_grupo_habilitado(
    tmp_path, sample_expert, sample_homologos
):
    output_dir = tmp_path / "output"
    results, warnings = run_homologos_filter(sample_expert, sample_homologos, output_dir)

    assert len(results) == 1
    result = results[0]
    assert result.grupo == "MP12"
    assert result.filas_filtradas == 2
    assert result.xlsx_path == output_dir / "MP12_ready.xlsx"
    assert result.csv_path == output_dir / "MP12_ready.csv"
    assert result.xlsx_path.exists()
    assert result.csv_path.exists()

    # MP14 esta en el archivo de homologos pero no habilitado todavia (ver
    # ENABLED_GRUPOS) - debe generar advertencia y no archivo.
    assert any("MP14" in w and "no esta habilitado" in w for w in warnings)
    assert not (output_dir / "MP14_ready.xlsx").exists()


def test_run_homologos_filter_csv_tiene_el_mismo_formato_que_passthrough(
    tmp_path, sample_expert, sample_homologos
):
    output_dir = tmp_path / "output"
    results, _ = run_homologos_filter(sample_expert, sample_homologos, output_dir)

    csv_bytes = results[0].csv_path.read_bytes()
    text = csv_bytes.decode("iso-8859-1")
    assert "\r\n" in text
    lines = [line for line in text.split("\r\n") if line]
    assert lines[0] == ",".join(EXPERT_HEADER)
    assert lines[1].startswith("TINT1,")
    assert lines[2].startswith("TINT3,")
