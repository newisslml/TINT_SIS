from __future__ import annotations

from sqlalchemy.orm import Session

from tint_sis.canonical.models import FormulaCanonica
from tint_sis.db.models import Batch, FormulaRecord, GeneratedFileRecord, ValidationIssueRecord
from tint_sis.validation.rules import ValidationIssue


def create_batch(session: Session, origen_dir: str) -> Batch:
    batch = Batch(origen_dir=origen_dir)
    session.add(batch)
    session.flush()
    return batch


def save_formulas(session: Session, batch: Batch, formulas: list[FormulaCanonica]) -> None:
    for formula in formulas:
        record = FormulaRecord(
            batch_id=batch.id,
            linea_producto=formula.linea_producto,
            origen_archivo=formula.origen_archivo,
            origen_fila=formula.origen_fila,
            familia=formula.familia,
            clasificacion=formula.clasificacion,
            producto=formula.producto,
            cartilla=formula.cartilla,
            formato=formula.formato,
            tolerancia_luz=formula.tolerancia_luz,
            primer=formula.primer,
            color=formula.color,
            r=formula.r,
            g=formula.g,
            b=formula.b,
            base=formula.base,
            oz_base=formula.oz_base,
            colorantes_json=[c.model_dump() for c in formula.colorantes],
            metadata_json=formula.metadata,
        )
        session.add(record)


def save_issues(session: Session, batch: Batch, issues: list[ValidationIssue]) -> None:
    for issue in issues:
        session.add(
            ValidationIssueRecord(
                batch_id=batch.id,
                severity=issue.severity,
                mensaje=issue.mensaje,
                linea_producto=issue.linea_producto,
                origen_archivo=issue.origen_archivo,
                origen_fila=issue.origen_fila,
            )
        )


def record_generated_file(session: Session, batch: Batch, linea_producto: str, adaptador: str, ruta: str) -> None:
    session.add(
        GeneratedFileRecord(
            batch_id=batch.id,
            linea_producto=linea_producto,
            adaptador=adaptador,
            ruta=ruta,
        )
    )
