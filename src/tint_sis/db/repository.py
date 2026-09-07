from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tint_sis.db.models import Batch, GeneratedFileRecord


def get_last_batch(session: Session) -> Batch | None:
    return session.scalars(select(Batch).order_by(Batch.id.desc()).limit(1)).first()


def list_batches(session: Session, limit: int = 50) -> list[Batch]:
    return list(session.scalars(select(Batch).order_by(Batch.id.desc()).limit(limit)))


def files_for_batch(session: Session, batch: Batch) -> list[GeneratedFileRecord]:
    return list(
        session.scalars(
            select(GeneratedFileRecord)
            .where(GeneratedFileRecord.batch_id == batch.id)
            .order_by(GeneratedFileRecord.id)
        )
    )


def create_batch(session: Session, origen_dir: str) -> Batch:
    batch = Batch(origen_dir=origen_dir)
    session.add(batch)
    session.flush()
    return batch


def record_generated_file(session: Session, batch: Batch, linea_producto: str, adaptador: str, ruta: str) -> None:
    session.add(
        GeneratedFileRecord(
            batch_id=batch.id,
            linea_producto=linea_producto,
            adaptador=adaptador,
            ruta=ruta,
        )
    )
