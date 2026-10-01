import threading

import pytest

from tint_sis.app import _avisos


@pytest.fixture(autouse=True)
def sin_windows(monkeypatch):
    """Ningun test muestra notificaciones de Windows: se cuenta cuantas saldrian."""
    llamadas = []
    monkeypatch.setattr(
        _avisos, "_notificar_windows", lambda titulo, texto, nivel="ok": llamadas.append((titulo, texto))
    )
    monkeypatch.setattr(_avisos, "_sistema", False)
    return llamadas


def _esperar_hilos():
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(timeout=2)


def test_la_ui_recibe_solo_los_avisos_nuevos():
    inicio = _avisos.desde(-1)
    assert inicio["avisos"] == []  # al cargar la UI no se repiten avisos viejos
    a = _avisos.avisar("Ciclo terminado", "12 archivos generados", vista="resultados")
    b = _avisos.avisar("Expertos preparados", "listos", nivel="ok", vista="nuevo-ciclo")
    r = _avisos.desde(inicio["ultimo"])
    assert [x["titulo"] for x in r["avisos"]] == ["Ciclo terminado", "Expertos preparados"]
    assert r["ultimo"] == b["id"] == a["id"] + 1
    assert _avisos.desde(r["ultimo"])["avisos"] == []


def test_windows_solo_si_la_app_lo_activo_y_la_config_lo_permite(sin_windows, monkeypatch):
    _avisos.avisar("Ciclo terminado", "x")
    _esperar_hilos()
    assert sin_windows == []  # tests / CLI: nunca

    monkeypatch.setattr(_avisos, "_sistema", True)
    _avisos.avisar("Ciclo terminado", "x", sistema=False)  # notificaciones apagadas en Configuracion
    _avisos.avisar("Expertos preparados", "y")
    _esperar_hilos()
    assert sin_windows == [("Expertos preparados", "y")]


def test_script_de_la_notificacion_escapa_el_texto():
    script = _avisos._script_toast("Ciclo <terminado>", "Experto_1: 'galón' & más")
    assert "&lt;terminado&gt;" in script
    assert "''galón'' &amp; más" in script  # comilla simple doble dentro del string de PowerShell
    assert f"CreateToastNotifier('{_avisos.AUMID}')" in script
    assert "reminder" not in script


def test_advertencias_y_errores_quedan_en_pantalla_hasta_cerrarlas():
    script = _avisos._script_toast("Falta un experto", "Falta Experto 2", "advertencia")
    assert "<toast scenario=\"reminder\">" in script and "⚠ Falta un experto" in script
    assert 'activationType="system" arguments="dismiss"' in script


def _ciclo_con(monkeypatch, advertencias, archivos=1):
    """Corre _runner._run con un pipeline falso que devuelve esas advertencias."""
    from tint_sis.app import _runner
    from tint_sis.config import AppConfig
    from tint_sis.pipeline import GeneratedFile, PipelineSummary

    summary = PipelineSummary(
        advertencias=advertencias,
        archivos=[GeneratedFile("MP14", ".xlsx", 3, "x.xlsx", "Corob_Tint")] * archivos,
    )
    monkeypatch.setattr(_runner, "run_pipeline", lambda **kw: summary)
    ultimo = _avisos.desde(-1)["ultimo"]
    _runner._run(AppConfig())
    return _avisos.desde(ultimo)["avisos"]


def test_ciclo_sin_advertencias_avisa_en_verde(monkeypatch):
    [aviso] = _ciclo_con(monkeypatch, [])
    assert (aviso["titulo"], aviso["nivel"]) == ("Ciclo terminado", "ok")


def test_falta_un_experto_se_notifica_aparte_en_naranjo(monkeypatch):
    from tint_sis.pipeline import TIPO_EXPERTO, Advertencia

    avisos = _ciclo_con(
        monkeypatch,
        [
            Advertencia("Falta Experto 2 (Experto_2*.xls[xm]) en la carpeta de entrada: se omiten Tinwise_Lab",
                        tipo=TIPO_EXPERTO),
            Advertencia("Experto_1.xlsx: 4 filas de 1 producto(s) que no estan en homologos_TINT.xlsx", ["X (4 filas)"]),
        ],
    )
    assert [(a["titulo"], a["nivel"]) for a in avisos] == [
        ("Ciclo terminado", "advertencia"),
        ("Falta un experto", "advertencia"),
    ]
    assert "2 advertencias" in avisos[0]["texto"]
    assert "Falta Experto 2" in avisos[1]["texto"] and "Tinwise_Lab" in avisos[1]["texto"]
