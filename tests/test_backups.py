import datetime
import os
import sys

import pytest

from tint_sis.backups import FORMATO_CARPETA, RespaldoError, carpeta_backups, respaldar_filtrados
from tint_sis.db import repository
from tint_sis.db.database import get_session
from tint_sis.db.models import Batch

# asi vuelve creado_en de SQLite: naive, en UTC
CREADO = datetime.datetime(2026, 9, 23, 18, 14, 9)


def _nombre_local(dt_utc: datetime.datetime) -> str:
    return dt_utc.replace(tzinfo=datetime.timezone.utc).astimezone().strftime(FORMATO_CARPETA)


def _archivos(raiz):
    return sorted(str(p.relative_to(raiz)).replace("\\", "/") for p in raiz.rglob("*") if p.is_file())


@pytest.fixture
def filtrados(tmp_path):
    """<data>/output/Archivos filtrados con dos softwares, como deja un ciclo."""
    raiz = tmp_path / "data" / "output" / "Archivos filtrados"
    for rel in ("Santint/Tiendas 14_ready.xlsx", "Color_Pro3.1.1/MP12_ready.csv", "Color_Pro3.1.1/MP14_ready.csv"):
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text(rel, encoding="utf-8")
    return raiz


@pytest.fixture
def session(tmp_path):
    s = get_session(tmp_path / "t.db")
    yield s
    s.close()


def _ciclo(session, filtrados, creado=CREADO, rels=None):
    batch = Batch(origen_dir="in", creado_en=creado)
    session.add(batch)
    session.flush()
    for rel in rels if rels is not None else _archivos(filtrados):
        repository.record_generated_file(session, batch, "T", "a", str(filtrados / rel))
    session.commit()
    return batch


def test_backups_va_junto_a_la_carpeta_de_salida(tmp_path):
    assert carpeta_backups(tmp_path / "data" / "output") == tmp_path / "data" / "backups"


def test_mueve_todo_a_la_fecha_del_ultimo_ciclo_y_actualiza_la_base(tmp_path, filtrados, session):
    antes = _archivos(filtrados)
    batch = _ciclo(session, filtrados)
    backups = tmp_path / "data" / "backups"

    destino = respaldar_filtrados(filtrados, backups, session)

    assert destino == backups / _nombre_local(CREADO)
    assert _archivos(destino) == antes
    assert (destino / "Santint" / "Tiendas 14_ready.xlsx").read_text(encoding="utf-8") == "Santint/Tiendas 14_ready.xlsx"
    # filtrados queda vacio (sin las carpetas de software) para el ciclo nuevo
    assert filtrados.is_dir() and list(filtrados.iterdir()) == []
    rutas = {r.ruta for r in repository.files_for_batch(session, batch)}
    assert rutas == {str(destino / rel) for rel in antes}


def test_sin_archivos_no_crea_nada(tmp_path, session):
    vacia = tmp_path / "Archivos filtrados"
    (vacia / "Santint").mkdir(parents=True)
    backups = tmp_path / "backups"
    assert respaldar_filtrados(vacia, backups, session) is None
    assert respaldar_filtrados(tmp_path / "no-existe", backups, session) is None
    assert not backups.exists()


def test_no_toca_las_carpetas_excluidas(tmp_path, filtrados, session):
    (filtrados / ".staging" / "Experto 1").mkdir(parents=True)
    (filtrados / ".staging" / "Experto 1" / "MP12.xlsx").write_text("x", encoding="utf-8")

    destino = respaldar_filtrados(filtrados, tmp_path / "backups", session, excluir=(".staging",))

    assert not (destino / ".staging").exists()
    assert (filtrados / ".staging" / "Experto 1" / "MP12.xlsx").exists()


def test_sin_ciclo_registrado_usa_la_fecha_de_modificacion(tmp_path, filtrados, session):
    # p. ej. lo que dejo un ciclo cancelado: no quedo registrado en la base
    mtime = datetime.datetime(2026, 9, 20, 9, 5).timestamp()
    for p in filtrados.rglob("*.*"):
        os.utime(p, (mtime, mtime))

    destino = respaldar_filtrados(filtrados, tmp_path / "backups", session)

    assert destino.name == "2026-09-20_09-05"


def test_si_la_carpeta_ya_existe_agrega_sufijo(tmp_path, filtrados, session):
    _ciclo(session, filtrados)
    backups = tmp_path / "backups"
    (backups / _nombre_local(CREADO)).mkdir(parents=True)

    destino = respaldar_filtrados(filtrados, backups, session)

    assert destino.name == _nombre_local(CREADO) + "_2"


def test_la_fecha_es_la_del_ciclo_mas_nuevo_que_genero_los_archivos(tmp_path, filtrados, session):
    # antes del respaldo cada ciclo pisaba la misma ruta: el registro vigente es el mas nuevo
    viejo = _ciclo(session, filtrados, creado=datetime.datetime(2026, 9, 10, 12, 0))
    nuevo = _ciclo(session, filtrados)

    destino = respaldar_filtrados(filtrados, tmp_path / "backups", session)

    assert destino.name == _nombre_local(CREADO)
    assert all(str(destino) in r.ruta for r in repository.files_for_batch(session, nuevo))
    assert all("Archivos filtrados" in r.ruta for r in repository.files_for_batch(session, viejo))


@pytest.mark.skipif(sys.platform != "win32", reason="en Windows un archivo abierto no se puede mover")
def test_archivo_abierto_revierte_todo(tmp_path, filtrados, session):
    antes = _archivos(filtrados)
    batch = _ciclo(session, filtrados)
    rutas_antes = {r.ruta for r in repository.files_for_batch(session, batch)}
    backups = tmp_path / "backups"

    with open(filtrados / "Color_Pro3.1.1" / "MP14_ready.csv", encoding="utf-8"):
        with pytest.raises(RespaldoError, match="MP14_ready.csv"):
            respaldar_filtrados(filtrados, backups, session)

    assert _archivos(filtrados) == antes
    assert not (backups / _nombre_local(CREADO)).exists()
    session.expire_all()
    assert {r.ruta for r in repository.files_for_batch(session, batch)} == rutas_antes
