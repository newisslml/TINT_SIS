from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tint_sis.db.models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "tint_sis.db"


def get_engine(db_path: Path = DEFAULT_DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: Path = DEFAULT_DB_PATH) -> Session:
    engine = get_engine(db_path)
    factory = sessionmaker(bind=engine)
    return factory()
