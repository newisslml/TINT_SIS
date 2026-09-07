from __future__ import annotations

from sqlalchemy.orm import Session

from tint_sis.db.models import Batch, GeneratedFileRecord


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
