"""Rutas por defecto de TINT_SIS segun se ejecute desde el repo o como .exe (PyInstaller).

Congelada, la app vive en una carpeta de solo lectura (Program Files), asi que los
datos del usuario van a Documentos\\TINT_SIS y la base/config/logs a %LOCALAPPDATA%\\TINT_SIS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TINT_SIS"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".config" / "tint_sis"


def _documents_dir() -> Path:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        # CSIDL_PERSONAL = 5: respeta la redireccion de Documentos (p. ej. OneDrive)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    return Path.home() / "Documents"


def default_data_dir() -> Path:
    if is_frozen():
        return _documents_dir() / APP_NAME
    return _REPO_ROOT / "data"


def default_db_path() -> Path:
    if is_frozen():
        return app_data_dir() / "tint_sis.db"
    return default_data_dir() / "tint_sis.db"
