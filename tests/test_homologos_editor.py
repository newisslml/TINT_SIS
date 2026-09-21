import openpyxl
import pytest

from tint_sis.adapters.homologos_editor import (
    HomologosEditor,
    compute_cobertura,
    list_sheet_names,
    parse_sheet,
)


def _build_sample(path):
    """Reproduce la estructura real de homologos_TINT.xlsx: titulo, tabla de
    lineas (catalogo), y por cada linea una seccion con encabezado de metadatos
    ("ID,C,5" ...), filas de homologo y filas de ID_TINT debajo. Incluye un
    homologo pendiente (sin IDs) como el que ya existe en el archivo real."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MP12"
    ws.append(["LISTADO PRODUCTOS HOMOLOGOS TWIST MP+ 12"])
    ws.append([])
    ws.append([])
    ws.append(["PRODUCTOS", "ID_TINT", "ID", "CODE", "DESCR", "PATH"])
    ws.append([None, None, 1, "Latex", "Latex", "PROD0001"])
    ws.append([None, None, 2, "Esmaltes", "Esmaltes", "PROD0002"])
    ws.append([])
    ws.append([])
    ws.append(["Latex -  PROD0001", None, "ID,C,5", "CODE,C,34", "DESCR,C,34", "PATH,C,12"])
    ws.append([None, None, 4, "Habitacional Ceresita", "Habitacional Ceresita", "SUBP0004"])
    ws.append([None, "LatHab001", None, "Habitacional Ceresita"])
    ws.append([None, "LatHab002", None, "Habitacional Ceresita"])
    ws.append([])
    ws.append([None, None, 11, "Cereluxe Ceresita (BS)", "Cereluxe Ceresita (BS)", "SUBP0011"])
    ws.append([None, "EsmSCereluxe Aquatech001", None, "Cereluxe Ceresita (BS)"])
    ws.append([])
    ws.append([None, None, None, "Tecnoconstruccion Mate Sipa", "Tecnoconstruccion Mate Sipa", None])
    ws.append([])
    ws.append(["Esmaltes -  PROD0002", None, "ID,C,5", "CODE,C,34", "DESCR,C,34", "PATH,C,12"])
    ws.append([None, None, 1, "Semi Mate", "Semi Mate", "SUBP0001"])
    ws.append([None, "EsmSemiMate001", None, "Semi Mate"])

    ws2 = wb.create_sheet("MP14")
    ws2.append(["PRODUCTOS", "ID_TINT", "ID", "CODE", "DESCR", "PATH"])
    ws2.append([None, None, 1, "Latex", "Latex", "PROD0001"])
    ws2.append(["Latex -  PROD0001", None, "ID,C,5", "CODE,C,34", "DESCR,C,34", "PATH,C,12"])
    ws2.append([None, None, 4, "Habitacional Ceresita", "Habitacional Ceresita", "SUBP0004"])
    ws2.append([None, "LatHab001", None, "Habitacional Ceresita"])

    wb.save(path)


@pytest.fixture
def sample_path(tmp_path):
    path = tmp_path / "homologos_TINT.xlsx"
    _build_sample(path)
    return path


def test_list_sheet_names(sample_path):
    assert list_sheet_names(sample_path) == ["MP12", "MP14"]


def test_parse_sheet_lineas_y_homologos(sample_path):
    sheet = parse_sheet(sample_path, "MP12")
    assert sheet.titulo == "LISTADO PRODUCTOS HOMOLOGOS TWIST MP+ 12"
    assert [l.nombre for l in sheet.lineas] == ["Latex", "Esmaltes"]

    latex = sheet.lineas[0]
    assert [h.nombre for h in latex.homologos] == [
        "Habitacional Ceresita",
        "Cereluxe Ceresita (BS)",
        "Tecnoconstruccion Mate Sipa",
    ]
    assert latex.homologos[0].ids == ["LatHab001", "LatHab002"]
    assert latex.homologos[1].ids == ["EsmSCereluxe Aquatech001"]

    # homologo sin ID numerico y sin filas de ID debajo: "pendiente" (caso real
    # confirmado en el archivo maestro, ej. "Tecnoconstruccion Mate Sipa")
    pendiente = latex.homologos[2]
    assert pendiente.id_num is None
    assert pendiente.pendiente is True
    assert pendiente.ids == []


def test_parse_sheet_no_mezcla_lineas_distintas(sample_path):
    sheet = parse_sheet(sample_path, "MP12")
    esmaltes = sheet.lineas[1]
    assert [h.nombre for h in esmaltes.homologos] == ["Semi Mate"]
    assert esmaltes.homologos[0].ids == ["EsmSemiMate001"]


def test_compute_cobertura(sample_path):
    sheet = parse_sheet(sample_path, "MP12")
    expert_ids = {"LatHab001", "LatHab002", "EsmSCereluxe Aquatech001", "EsmSemiMate001", "SinAsignar001"}
    cobertura = compute_cobertura(sheet, expert_ids)

    assert cobertura["ids_sin_asignar"] == ["SinAsignar001"]
    assert cobertura["ids_no_en_experto"] == []
    assert cobertura["ids_duplicados"] == []
    assert {h["homologo"] for h in cobertura["homologos_sin_ids"]} == {"Tecnoconstruccion Mate Sipa"}


def test_compute_cobertura_detecta_duplicados_y_obsoletos(sample_path):
    sheet = parse_sheet(sample_path, "MP12")
    homologos_por_nombre = {h.nombre: h for l in sheet.lineas for h in l.homologos}
    homologos_por_nombre["Semi Mate"].id_rows.append((999, "LatHab001"))  # duplicar a mano

    cobertura = compute_cobertura(sheet, expert_ids=set())
    assert cobertura["ids_no_en_experto"]  # todos, porque expert_ids esta vacio
    dup = next(d for d in cobertura["ids_duplicados"] if d["id_tint"] == "LatHab001")
    assert {a["homologo"] for a in dup["asignaciones"]} == {"Habitacional Ceresita", "Semi Mate"}


# --------------------------------------------------------------------------- #
# HomologosEditor
# --------------------------------------------------------------------------- #
def _reabrir(path, tienda):
    """Vuelve a leer el archivo desde disco (no desde la cache del editor) para
    confirmar que los cambios realmente se escribieron."""
    return parse_sheet(path, tienda)


def test_agregar_id(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", " LatHab003 ")
    sheet = editor.arbol("MP12")
    homologo = next(h for l in sheet.lineas for h in l.homologos if h.nombre == "Habitacional Ceresita")
    assert homologo.ids == ["LatHab001", "LatHab002", "LatHab003"]
    assert editor.dirty is True


def test_agregar_id_a_homologo_pendiente(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_id("MP12", "Latex", "Tecnoconstruccion Mate Sipa", "NuevoID001")
    sheet = editor.arbol("MP12")
    homologo = next(h for l in sheet.lineas for h in l.homologos if h.nombre == "Tecnoconstruccion Mate Sipa")
    assert homologo.ids == ["NuevoID001"]
    assert homologo.pendiente is False


def test_agregar_id_duplicado_falla(sample_path):
    editor = HomologosEditor(sample_path)
    with pytest.raises(ValueError, match="ya esta asignado"):
        editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab001")


def test_agregar_id_no_afecta_otras_hojas(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab003")
    mp14 = editor.arbol("MP14")
    homologo = mp14.lineas[0].homologos[0]
    assert homologo.ids == ["LatHab001"]


def test_quitar_id(sample_path):
    editor = HomologosEditor(sample_path)
    editor.quitar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab001")
    sheet = editor.arbol("MP12")
    homologo = next(h for l in sheet.lineas for h in l.homologos if h.nombre == "Habitacional Ceresita")
    assert homologo.ids == ["LatHab002"]


def test_quitar_id_inexistente_falla(sample_path):
    editor = HomologosEditor(sample_path)
    with pytest.raises(ValueError, match="no esta asignado"):
        editor.quitar_id("MP12", "Latex", "Habitacional Ceresita", "NoExiste")


def test_agregar_homologo_nuevo_queda_pendiente(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_homologo("MP12", "Latex", "Nuevo Homologo")
    sheet = editor.arbol("MP12")
    linea = sheet.lineas[0]
    assert linea.homologos[-1].nombre == "Nuevo Homologo"
    assert linea.homologos[-1].pendiente is True
    # no debe mezclarse con la siguiente linea (Esmaltes sigue igual)
    assert [h.nombre for h in sheet.lineas[1].homologos] == ["Semi Mate"]


def test_agregar_homologo_duplicado_falla(sample_path):
    editor = HomologosEditor(sample_path)
    with pytest.raises(ValueError, match="Ya existe"):
        editor.agregar_homologo("MP12", "Latex", "Habitacional Ceresita")


def test_agregar_linea_nueva(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_linea("MP12", "Barnices")
    sheet = editor.arbol("MP12")
    assert sheet.lineas[-1].nombre == "Barnices"
    assert sheet.lineas[-1].pendiente is True
    assert sheet.lineas[-1].path == "PROD0003"

    # las lineas viejas no se ven afectadas
    assert sheet.lineas[0].homologos[0].ids == ["LatHab001", "LatHab002"]

    # se le puede agregar un homologo a la linea recien creada
    editor.agregar_homologo("MP12", "Barnices", "Homologo Nuevo")
    sheet = editor.arbol("MP12")
    assert sheet.lineas[-1].homologos[0].nombre == "Homologo Nuevo"


def test_agregar_linea_duplicada_falla(sample_path):
    editor = HomologosEditor(sample_path)
    with pytest.raises(ValueError, match="Ya existe"):
        editor.agregar_linea("MP12", "Latex")


def test_guardar_hace_backup_y_persiste_en_disco(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab003")
    backup = editor.guardar()

    assert backup.exists()
    assert editor.dirty is False

    releido = _reabrir(sample_path, "MP12")
    homologo = next(h for l in releido.lineas for h in l.homologos if h.nombre == "Habitacional Ceresita")
    assert homologo.ids == ["LatHab001", "LatHab002", "LatHab003"]

    # el backup tiene el contenido de ANTES del cambio
    backup_sheet = _reabrir(backup, "MP12")
    homologo_backup = next(h for l in backup_sheet.lineas for h in l.homologos if h.nombre == "Habitacional Ceresita")
    assert homologo_backup.ids == ["LatHab001", "LatHab002"]


def test_guardar_preserva_hojas_no_tocadas(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab003")
    editor.guardar()

    mp14 = _reabrir(sample_path, "MP14")
    assert mp14.lineas[0].homologos[0].ids == ["LatHab001"]


def test_multiples_ediciones_antes_de_guardar(sample_path):
    editor = HomologosEditor(sample_path)
    editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab003")
    editor.agregar_homologo("MP12", "Esmaltes", "Otro Homologo")
    editor.agregar_linea("MP12", "Chilcorrofin")
    editor.agregar_id("MP12", "Latex", "Habitacional Ceresita", "LatHab004")
    editor.guardar()

    sheet = _reabrir(sample_path, "MP12")
    homologo = next(h for l in sheet.lineas for h in l.homologos if h.nombre == "Habitacional Ceresita")
    assert homologo.ids == ["LatHab001", "LatHab002", "LatHab003", "LatHab004"]
    assert any(h.nombre == "Otro Homologo" for l in sheet.lineas for h in l.homologos)
    assert any(l.nombre == "Chilcorrofin" for l in sheet.lineas)
