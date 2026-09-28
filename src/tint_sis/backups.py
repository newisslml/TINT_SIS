"""Respaldo de las salidas del ciclo anterior.

Cuando un ciclo nuevo va a generar archivos, todo lo que hay en la carpeta de
filtrados (<salida>/Archivos filtrados/) se mueve a <data>/backups/<fecha>/, con
<fecha> = la del ultimo ciclo que genero esos archivos. Asi la carpeta de
filtrados queda solo con lo del ciclo nuevo y cada ciclo viejo conserva sus
archivos (antes el ciclo nuevo los pisaba). Los registros de la base se apuntan a
la ruta nueva para que Historial abra el backup.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from tint_sis.db.models import Batch, GeneratedFileRecord

BACKUPS_DIRNAME = "backups"
# sin ":" (no se permite en nombres de carpeta de Windows); ordena cronologicamente
FORMATO_CARPETA = "%Y-%m-%d_%H-%M"


class RespaldoError(Exception):
    """No se pudo mover algun archivo al backup (tipicamente, abierto en Excel).
    El respaldo se revierte entero: los archivos quedan donde estaban."""


def carpeta_backups(output_dir: Path) -> Path:
    """<data>/backups: hermana de la carpeta de salida (<data>/output)."""
    return Path(output_dir).parent / BACKUPS_DIRNAME


def clave_ruta(ruta: str | Path) -> str:
    """Forma comparable de una ruta (Windows no distingue mayusculas)."""
    return os.path.normcase(os.path.abspath(ruta))


def _local(dt: datetime.datetime) -> datetime.datetime:
    # creado_en se guarda en UTC y vuelve naive de SQLite
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone()


def _excluido(ruta: Path, raiz: Path, excluir: tuple[str, ...]) -> bool:
    return any(parte in excluir for parte in ruta.relative_to(raiz).parts)


def _borrar_carpetas_vacias(raiz: Path, excluir: tuple[str, ...] = (), incluir_raiz: bool = False) -> None:
    for actual, _dirs, _files in os.walk(raiz, topdown=False):
        carpeta = Path(actual)
        if (carpeta == raiz and not incluir_raiz) or _excluido(carpeta, raiz, excluir):
            continue
        try:
            carpeta.rmdir()  # solo borra si esta vacia
        except OSError:
            pass


def respaldar_filtrados(
    filtrados: Path, backups: Path, session: Session, excluir: tuple[str, ...] = ()
) -> Path | None:
    """Mueve todo lo de `filtrados` (menos las carpetas `excluir`) a
    `backups`/<fecha del ultimo ciclo>/, conservando la subcarpeta de cada
    software. Devuelve la carpeta del backup, o None si no habia nada que mover.

    La fecha es la del ciclo mas nuevo registrado en la base que genero alguno de
    esos archivos; si ninguno esta registrado (corrida cancelada, base nueva), la
    de modificacion del archivo mas nuevo. Si la carpeta ya existe se agrega _2,
    _3... Si algun archivo no se puede mover se revierte todo y se lanza
    RespaldoError, antes de tocar la base."""
    filtrados = Path(filtrados)
    if not filtrados.is_dir():
        return None
    archivos = [p for p in filtrados.rglob("*") if p.is_file() and not _excluido(p, filtrados, excluir)]
    if not archivos:
        return None

    # registro vigente de cada archivo: el del ciclo mas nuevo que lo genero (los
    # ciclos anteriores escribian en la misma ruta y ese archivo ya no existe)
    por_clave = {clave_ruta(p): p for p in archivos}
    vigentes: dict[str, GeneratedFileRecord] = {}
    for reg in session.scalars(select(GeneratedFileRecord)):
        clave = clave_ruta(reg.ruta)
        if clave in por_clave and (clave not in vigentes or reg.batch_id > vigentes[clave].batch_id):
            vigentes[clave] = reg

    if vigentes:
        fecha = _local(session.get(Batch, max(r.batch_id for r in vigentes.values())).creado_en)
    else:
        fecha = datetime.datetime.fromtimestamp(max(p.stat().st_mtime for p in archivos))
    nombre = fecha.strftime(FORMATO_CARPETA)
    destino = Path(backups) / nombre
    n = 2
    while destino.exists():
        destino = Path(backups) / f"{nombre}_{n}"
        n += 1

    movidos: list[tuple[Path, Path]] = []
    for origen in archivos:
        nuevo = destino / origen.relative_to(filtrados)
        try:
            nuevo.parent.mkdir(parents=True, exist_ok=True)
            os.replace(origen, nuevo)
        except OSError as exc:
            for de, a in reversed(movidos):
                try:
                    os.replace(a, de)
                except OSError:
                    pass
            _borrar_carpetas_vacias(destino, incluir_raiz=True)
            raise RespaldoError(
                f"No se pudo mover {origen.relative_to(filtrados)} al backup ({exc.strerror or exc}). "
                "Si esta abierto (por ejemplo en Excel), cerrarlo y volver a ejecutar el ciclo. "
                "No se movio ni se genero nada."
            ) from exc
        movidos.append((origen, nuevo))

    for clave, reg in vigentes.items():
        reg.ruta = str(destino / por_clave[clave].relative_to(filtrados))
    session.commit()

    _borrar_carpetas_vacias(filtrados, excluir)
    return destino
