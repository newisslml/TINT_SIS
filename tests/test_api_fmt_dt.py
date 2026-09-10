import datetime

from tint_sis.app.api import _fmt_dt


def test_none_devuelve_guion():
    assert _fmt_dt(None) == "-"


def test_naive_se_interpreta_como_utc_y_pasa_a_local():
    # asi vuelven creado_en / generado_en de SQLite: naive, en UTC
    naive_utc = datetime.datetime(2026, 9, 10, 19, 41, 24)
    aware_utc = naive_utc.replace(tzinfo=datetime.timezone.utc)

    esperado = aware_utc.astimezone().strftime("%Y-%m-%d %H:%M")
    assert _fmt_dt(naive_utc) == esperado
    # una fecha ya tz-aware debe dar el mismo instante local
    assert _fmt_dt(aware_utc) == esperado
