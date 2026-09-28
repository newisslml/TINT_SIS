import datetime

from tint_sis.app.api import FMT_FECHA_HISTORIAL, _fmt_dt


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


def test_formato_de_historial_dd_mm_yy():
    aware_utc = datetime.datetime(2026, 9, 28, 18, 9, tzinfo=datetime.timezone.utc)
    local = aware_utc.astimezone()
    assert _fmt_dt(aware_utc, FMT_FECHA_HISTORIAL) == local.strftime("%d/%m/%y %H:%M")
    assert _fmt_dt(aware_utc, FMT_FECHA_HISTORIAL).startswith(f"{local.day:02d}/{local.month:02d}/{local.year % 100:02d} ")
