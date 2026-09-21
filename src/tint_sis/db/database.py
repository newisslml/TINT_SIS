from __future__ import annotations

import threading
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tint_sis.db.models import Base
from tint_sis.paths import default_db_path

DEFAULT_DB_PATH = default_db_path()

# La API atiende requests en paralelo: sin esto, varios create_all sobre una base nueva chocan.
_engines: dict[Path, object] = {}
_engines_lock = threading.Lock()


def get_engine(db_path: Path = DEFAULT_DB_PATH):
    db_path = Path(db_path).resolve()
    with _engines_lock:
        engine = _engines.get(db_path)
        if engine is None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(engine)
            _engines[db_path] = engine
        return engine


def get_session(db_path: Path = DEFAULT_DB_PATH) -> Session:
    engine = get_engine(db_path)
    factory = sessionmaker(bind=engine)
    return factory()
