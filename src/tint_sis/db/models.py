from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    origen_dir: Mapped[str] = mapped_column(String(500))

    formulas: Mapped[list["FormulaRecord"]] = relationship(back_populates="batch")
    issues: Mapped[list["ValidationIssueRecord"]] = relationship(back_populates="batch")
    generated_files: Mapped[list["GeneratedFileRecord"]] = relationship(back_populates="batch")


class FormulaRecord(Base):
    __tablename__ = "formulas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))

    linea_producto: Mapped[str] = mapped_column(String(200), index=True)
    origen_archivo: Mapped[str] = mapped_column(String(300))
    origen_fila: Mapped[int] = mapped_column(Integer)

    familia: Mapped[str] = mapped_column(String(200))
    clasificacion: Mapped[str | None] = mapped_column(String(200), nullable=True)

    producto: Mapped[str] = mapped_column(String(300))
    cartilla: Mapped[str | None] = mapped_column(String(200), nullable=True)
    formato: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tolerancia_luz: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color: Mapped[str] = mapped_column(String(300))

    r: Mapped[int | None] = mapped_column(Integer, nullable=True)
    g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    b: Mapped[int | None] = mapped_column(Integer, nullable=True)

    base: Mapped[str | None] = mapped_column(String(200), nullable=True)
    oz_base: Mapped[float | None] = mapped_column(nullable=True)

    colorantes_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    batch: Mapped[Batch] = relationship(back_populates="formulas")


class ValidationIssueRecord(Base):
    __tablename__ = "validation_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))

    severity: Mapped[str] = mapped_column(String(20))
    mensaje: Mapped[str] = mapped_column(Text)
    linea_producto: Mapped[str] = mapped_column(String(200))
    origen_archivo: Mapped[str] = mapped_column(String(300))
    origen_fila: Mapped[int] = mapped_column(Integer)

    batch: Mapped[Batch] = relationship(back_populates="issues")


class GeneratedFileRecord(Base):
    __tablename__ = "generated_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))

    linea_producto: Mapped[str] = mapped_column(String(200))
    adaptador: Mapped[str] = mapped_column(String(100))
    ruta: Mapped[str] = mapped_column(String(500))
    generado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    batch: Mapped[Batch] = relationship(back_populates="generated_files")
