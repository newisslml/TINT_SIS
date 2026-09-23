"""El mapeo de eventos on_progress -> estado de la barra en la app."""
import time

import pytest

from tint_sis.app import _runner


def _fresh():
    with _runner._lock:
        _runner._reset_locked()
        _runner._state.estado = "en_curso"
        _runner._state.started_at = time.time()


def test_progreso_por_etapas_de_un_experto():
    _fresh()
    ev = _runner._on_progress

    ev({"fase": "inicio", "mensaje": "Filtro por productos", "total": 3})
    ev({"fase": "experto_inicio", "item": "Experto 1", "mensaje": "Experto 1: filtrando"})
    snap = _runner.snapshot()
    assert snap["expertos"][0]["experto"] == "Experto 1"
    assert 0 < snap["expertos"][0]["progreso"] <= 10

    # a mitad de la lectura del experto
    ev({"fase": "experto_progreso", "item": "Experto 1", "etapa": "filtrar", "leidas": 93000, "sub_total": 186000})
    p_filtrar = _runner.snapshot()["expertos"][0]["progreso"]
    assert 2 <= p_filtrar <= 50
    assert "filtrando experto" in _runner.snapshot()["expertos"][0]["texto"]

    # armando los libros filtrados (sin progreso fino)
    ev({"fase": "experto_progreso", "item": "Experto 1", "etapa": "guardar"})
    s = _runner.snapshot()["expertos"][0]
    assert s["progreso"] >= p_filtrar
    assert "guardando" in s["texto"].lower()

    # escribiendo el csv de Color Pro 3.1.1
    ev({"fase": "experto_progreso", "item": "Experto 1", "etapa": "csv", "leidas": 90000, "sub_total": 180000})
    s = _runner.snapshot()["expertos"][0]
    assert 70 <= s["progreso"] <= 99
    assert "CSV" in s["texto"]

    ev({"fase": "experto_ok", "item": "Experto 1", "mensaje": "Experto 1: MP14 120.000"})
    s = _runner.snapshot()["expertos"][0]
    assert s["progreso"] == 100
    assert s["texto"] == "listo"


def test_global_promedia_sobre_el_total_de_expertos():
    _fresh()
    ev = _runner._on_progress
    ev({"fase": "inicio", "mensaje": "Filtro por productos", "total": 3})
    ev({"fase": "experto_inicio", "item": "Experto 1", "mensaje": "x"})
    ev({"fase": "experto_progreso", "item": "Experto 1", "etapa": "csv", "leidas": 100, "sub_total": 100})
    # 1 de 3 expertos casi listo -> global bien por debajo de la mitad
    assert _runner.snapshot()["progreso_global"] <= 40


def test_creep_no_congela_la_barra_entre_eventos():
    _fresh()
    ev = _runner._on_progress
    ev({"fase": "inicio", "mensaje": "Filtro por productos", "total": 1})
    ev({"fase": "experto_inicio", "item": "Experto 3", "mensaje": "x"})
    ev({"fase": "experto_progreso", "item": "Experto 3", "etapa": "guardar"})
    base = _runner.snapshot()["expertos"][0]["progreso"]
    # simular que pasaron ~10s sin eventos
    with _runner._lock:
        _runner._state.expertos_seen["Experto 3"] = time.time() - 10
    despues = _runner.snapshot()["expertos"][0]["progreso"]
    assert despues > base
    assert despues <= 70  # no pasa el techo de la etapa guardar


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
            {"fase": "experto_progreso", "item": "Experto 3", "etapa": "filtrar", "leidas": 2000, "sub_total": 100000}
        )


def test_reset_limpia_una_cancelacion_previa():
    _runner._cancel.set()
    _fresh()  # _fresh -> _reset_locked, que debe limpiar la bandera
    assert not _runner._cancel.is_set()
    # y on_progress ya no aborta
    _runner._on_progress({"fase": "experto_inicio", "item": "Experto 3", "mensaje": "x"})
    assert _runner.snapshot()["expertos"][0]["experto"] == "Experto 3"
