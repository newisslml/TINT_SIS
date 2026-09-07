from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    origen_dir: Mapped[str] = mapped_column(String(500))

    generated_files: Mapped[list["GeneratedFileRecord"]] = relationship(back_populates="batch")


class GeneratedFileRecord(Base):
    __tablename__ = "generated_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))

    linea_producto: Mapped[str] = mapped_column(String(200))
    adaptador: Mapped[str] = mapped_column(String(100))
    ruta: Mapped[str] = mapped_column(String(500))
    generado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    batch: Mapped[Batch] = relationship(back_populates="generated_files")
