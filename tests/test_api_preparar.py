import time

import pytest
from fastapi import HTTPException

from libros_prueba import carpeta_preparacion
from tint_sis.app import _preparar, api
from tint_sis.config import AppConfig


def _esperar(estados, timeout=60):
    fin = time.time() + timeout
    while time.time() < fin:
        s = api.get_preparar_estado()
        if s["estado"] in estados:
            return s
        time.sleep(0.1)
    raise AssertionError(f"timeout esperando {estados}: {api.get_preparar_estado()['estado']}")


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    inp, maestro = carpeta_preparacion(tmp_path / "data")
    cfg = AppConfig(input_dir=inp, output_dir=tmp_path / "data" / "output", db_path=tmp_path / "t.db")
    monkeypatch.setattr(api, "_cfg", lambda: cfg)
    _preparar.reiniciar()
    yield cfg, maestro
    _esperar({"idle", "analizado", "listo", "error"})
    _preparar.reiniciar()


@pytest.mark.parametrize(
    "nombre, entrada",
    [
        ("Experto_1_28_09_2026.xlsx", True),
        ("Experto_1.xls", True),  # va a la entrada para que el preview avise del .xls
        ("Experto_2_28_09_2026.xlsm", True),
        ("Experto_3.xlsx", True),
        ("productos_TINT.xlsx", True),
        ("homologos_TINT.xlsx", True),
        ("xData_DATACOMPLETA_10_09_2026.xlsx", True),
        ("Todo  MP14 28092026.xlsx", False),
        ("Todo  MP14 28092026 (sin duplicados).xlsx", False),
        ("GARNITEX Y HOMOLOGOS 28092026.xlsx", False),
    ],
)
def test_que_archivo_va_a_la_entrada_y_cual_es_el_maestro(nombre, entrada):
    assert api.es_archivo_de_entrada(AppConfig(), nombre) is entrada


def test_dropzone_de_nuevo_ciclo_distingue_experto_y_maestro(cfg):
    from fastapi.testclient import TestClient

    from tint_sis.app.server import app

    config, maestro = cfg
    cliente = TestClient(app)

    r = cliente.post("/api/input/upload", files={"file": ("Experto_3_30_09_2026.xlsx", b"PK")})
    assert r.status_code == 200 and r.json()["tipo"] == "entrada"
    assert (config.input_dir / "Experto_3_30_09_2026.xlsx").exists()

    r = cliente.post("/api/input/upload", files={"file": ("Todo viejo.xls", b"x")})
    assert r.status_code == 400 and ".xlsx" in r.json()["detail"]

    r = cliente.post("/api/input/upload", files={"file": (maestro.name, maestro.read_bytes())})
    assert r.status_code == 200
    assert r.json()["tipo"] == "maestro"
    assert r.json()["preparar"]["estado"] == "analizando"
    assert (config.input_dir.parent / "maestros" / maestro.name).exists()
    assert not (config.input_dir / maestro.name).exists()
    (config.input_dir / "Experto_3_30_09_2026.xlsx").unlink()  # no es un libro valido
    s = _esperar({"analizado", "error"})
    assert s["estado"] == "analizado", s["error"]


def test_confirmar_sin_analisis_da_409(cfg):
    with pytest.raises(HTTPException) as exc:
        api.post_preparar_confirmar({"nuevos": {}})
    assert exc.value.status_code == 409


def test_analizar_y_preparar_en_segundo_plano(cfg):
    config, maestro = cfg
    assert api.get_preparar_estado()["estado"] == "idle"
    assert _preparar.iniciar_analisis(config, maestro)

    s = _esperar({"analizado", "error"})
    assert s["estado"] == "analizado", s["error"]
    assert s["analisis"]["nuevos"][0]["producto"] == "Texturex y Homologos"
    assert s["progreso"] == 100

    s = api.post_preparar_confirmar(
        {"nuevos": {"texturexyhomologos": {"tiendas": ["MP14"], "nombre_e2": "", "nombre_e3": "Texturas / Texturex"}}}
    )
    s = _esperar({"listo", "error"})
    assert s["estado"] == "listo", s["error"]
    assert [a["archivo"] for a in s["resultado"]["archivos"]] == [
        "Experto_1_28_09_2026.xlsx", "Experto_2_28_09_2026.xlsm", "Experto_3_28_09_2026.xlsx",
    ]
    assert s["resultado"]["productos_agregados"][0]["tiendas"] == ["MP14"]
    # nombre de Experto 2 vacio -> el del maestro
    assert s["resultado"]["productos_agregados"][0]["Experto 2"] == "Texturex y Homologos"

    _preparar.reiniciar()
    ultimo = api.get_preparar_estado()["ultimo"]
    assert ultimo["maestro"] == "Todo  MP14 28092026.xlsx"
    assert ultimo["nuevos"] == [{"linea": "Texturas", "producto": "Texturex y Homologos", "filas": 2}]
