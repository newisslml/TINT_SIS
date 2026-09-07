"""FastAPI local: expone `/api/*` y sirve la UI estatica de `ui/`."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router

UI_DIR = Path(__file__).parent / "ui"

app = FastAPI(title="TINT_SIS", docs_url=None, redoc_url=None)
app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
