"""El mapeo de eventos on_progress -> estado de la barra en la app."""
import time

import pytest

from tint_sis.app import _runner


def _fresh():
    with _runner._lock:
        _runner._reset_locked()
        _runner._state.estado = "en_curso"
        _runner._state.started_at = time.time()


def test_progreso_por_etapas_de_una_tienda():
    _fresh()
    ev = _runner._on_progress

    ev({"fase": "inicio", "mensaje": "Filtro por homologos", "total": 2})
    ev({"fase": "tienda_inicio", "item": "MP14", "mensaje": "Filtrando MP14"})
    snap = _runner.snapshot()
    assert snap["tiendas"][0]["grupo"] == "MP14"
    assert 0 < snap["tiendas"][0]["progreso"] <= 22

    # a mitad de la lectura del experto
    ev({"fase": "tienda_progreso", "item": "MP14", "etapa": "filtrar", "leidas": 93000, "sub_total": 186000})
    p_filtrar = _runner.snapshot()["tiendas"][0]["progreso"]
    assert 2 <= p_filtrar <= 22
    assert "filtrando experto" in _runner.snapshot()["tiendas"][0]["texto"]

    # guardando el xlsx (sin progreso fino)
    ev({"fase": "tienda_progreso", "item": "MP14", "etapa": "guardar_xlsx"})
    s = _runner.snapshot()["tiendas"][0]
    assert s["progreso"] >= p_filtrar
    assert "guardando" in s["texto"].lower()

    # escribiendo csv
    ev({"fase": "tienda_progreso", "item": "MP14", "etapa": "csv", "leidas": 90000, "sub_total": 180000})
    s = _runner.snapshot()["tiendas"][0]
    assert 75 <= s["progreso"] <= 99
    assert "CSV" in s["texto"]

    ev({"fase": "tienda_ok", "item": "MP14", "mensaje": "MP14: 120000 filas"})
    s = _runner.snapshot()["tiendas"][0]
    assert s["progreso"] == 100
    assert s["texto"] == "listo"


def test_global_promedia_sobre_el_total_de_tiendas():
    _fresh()
    ev = _runner._on_progress
    ev({"fase": "inicio", "mensaje": "Filtro por homologos", "total": 4})
    ev({"fase": "tienda_inicio", "item": "MP14", "mensaje": "x"})
    ev({"fase": "tienda_progreso", "item": "MP14", "etapa": "csv", "leidas": 100, "sub_total": 100})
    # 1 de 4 tiendas casi lista -> global bien por debajo de 100/4+algo
    assert _runner.snapshot()["progreso_global"] <= 30


def test_creep_no_congela_la_barra_entre_eventos():
    _fresh()
    ev = _runner._on_progress
    ev({"fase": "inicio", "mensaje": "Filtro por homologos", "total": 1})
    ev({"fase": "tienda_inicio", "item": "MP14", "mensaje": "x"})
    ev({"fase": "tienda_progreso", "item": "MP14", "etapa": "guardar_xlsx"})
    base = _runner.snapshot()["tiendas"][0]["progreso"]
    # simular que pasaron ~10s sin eventos
    with _runner._lock:
        _runner._state.tiendas_seen["MP14"] = time.time() - 10
    despues = _runner.snapshot()["tiendas"][0]["progreso"]
    assert despues > base
    assert despues <= 75  # no pasa el techo de la etapa guardar_xlsx


def test_request_cancel_sin_corrida_devuelve_false():
    with _runner._lock:
        _runner._reset_locked()
    assert _runner.request_cancel() is False


def test_cancel_hace_que_on_progress_corte_la_corrida():
    _fresh()
    assert _runner.request_cancel() is True
    # el proximo evento del motor debe abortar
    with pytest.raises(_runner.RunCancelled):
        _runner._on_progress(
            {"fase": "tienda_progreso", "item": "MP14", "etapa": "filtrar", "leidas": 2000, "sub_total": 100000}
        )


def test_reset_limpia_una_cancelacion_previa():
    _runner._cancel.set()
    _fresh()  # _fresh -> _reset_locked, que debe limpiar la bandera
    assert not _runner._cancel.is_set()
    # y on_progress ya no aborta
    _runner._on_progress({"fase": "tienda_inicio", "item": "MP14", "mensaje": "x"})
    assert _runner.snapshot()["tiendas"][0]["grupo"] == "MP14"
