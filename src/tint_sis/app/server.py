"""FastAPI local: expone `/api/*` y sirve la UI estatica de `ui/`."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from .api import router

UI_DIR = Path(__file__).parent / "ui"


class _NoCacheStatic(StaticFiles):
    """Sirve la UI sin cache. Es una app local de un solo usuario: no hay nada
    que ganar cacheando y, cuando se toca el HTML/CSS/JS, el WebView tiene que
    mostrar la version nueva si o si (el ETag de StaticFiles hacia que el
    navegador embebido siguiera con la copia vieja tras editar una vista)."""

    def file_response(self, *args, **kwargs) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
        for stale in ("etag", "last-modified"):
            if stale in resp.headers:
                del resp.headers[stale]
        return resp

    def is_not_modified(self, response_headers, request_headers) -> bool:  # noqa: ARG002
        return False


app = FastAPI(title="TINT_SIS", docs_url=None, redoc_url=None)
app.include_router(router, prefix="/api")
app.mount("/", _NoCacheStatic(directory=UI_DIR, html=True), name="ui")
