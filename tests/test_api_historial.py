import datetime

from tint_sis.app import api
from tint_sis.config import AppConfig
from tint_sis.db import repository
from tint_sis.db.database import get_session
from tint_sis.db.models import Batch


def _ciclo(session, dia, rutas):
    batch = Batch(origen_dir="in", creado_en=datetime.datetime(2026, 9, dia, 15, 0))
    session.add(batch)
    session.flush()
    for ruta in rutas:
        repository.record_generated_file(session, batch, "Tiendas 14", "Santint_xlsx", str(ruta))
    session.commit()


def test_historial_distingue_backups_y_ciclos_pisados(tmp_path, monkeypatch):
    data = tmp_path / "data"
    cfg = AppConfig(input_dir=data / "input", output_dir=data / "output", db_path=tmp_path / "t.db")
    monkeypatch.setattr(api, "_cfg", lambda: cfg)

    actual = data / "output" / "Archivos filtrados" / "Santint" / "Tiendas 14_ready.xlsx"
    respaldado = data / "backups" / "2026-09-22_12-00" / "Santint" / "Tiendas 14_ready.xlsx"
    for p in (actual, respaldado):
        p.parent.mkdir(parents=True)
        p.write_bytes(b"x")

    session = get_session(cfg.db_path)
    try:
        _ciclo(session, 20, [actual])  # previo al respaldo: su archivo lo piso el ciclo del 24
        _ciclo(session, 22, [respaldado])
        _ciclo(session, 24, [actual])
    finally:
        session.close()

    nuevo, backup, pisado = api.get_historial()["ciclos"]

    assert nuevo["n_disponibles"] == 1
    assert nuevo["carpeta"] == str(data / "output" / "Archivos filtrados")
    assert backup["n_disponibles"] == 1
    assert backup["carpeta"] == str(data / "backups" / "2026-09-22_12-00")
    assert backup["carpeta_existe"] is True
    assert pisado["n_disponibles"] == 0
    assert pisado["carpeta_existe"] is False
    assert pisado["grupos"][0]["salidas"][0]["existe"] is False
    # ciclos de antes de que se guardaran las advertencias
    assert nuevo["advertencias"] is None


def test_resultados_e_historial_listan_las_advertencias_guardadas(tmp_path, monkeypatch):
    cfg = AppConfig(input_dir=tmp_path / "input", output_dir=tmp_path / "output", db_path=tmp_path / "t.db")
    monkeypatch.setattr(api, "_cfg", lambda: cfg)
    monkeypatch.setattr(api._runner, "last_summary", lambda: None)  # como despues de reabrir la app
    avisos = [
        {"texto": "Experto_1.xlsx: 9 filas de 2 producto(s) que no estan en productos_TINT.xlsx",
         "detalle": ["Nuevo A (5 filas)", "Nuevo B (4 filas)"], "tipo": ""},
        {"texto": "Falta Experto 2", "detalle": [], "tipo": "experto"},
    ]
    session = get_session(cfg.db_path)
    try:
        _ciclo(session, 20, [])  # ciclo viejo: sin advertencias guardadas
        batch = Batch(origen_dir="in", creado_en=datetime.datetime(2026, 9, 24, 15, 0))
        session.add(batch)
        session.flush()
        repository.record_warnings(session, batch, avisos)
        session.commit()
    finally:
        session.close()

    r = api.get_resultados()
    assert r["resumen"]["advertencias"] == 2
    assert r["advertencias"] == avisos
    assert api.get_inicio()["ultimo_ciclo"]["advertencias"] == 2
    nuevo, viejo = api.get_historial()["ciclos"]
    assert nuevo["advertencias"] == avisos
    assert viejo["advertencias"] is None
