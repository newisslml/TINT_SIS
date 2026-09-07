"""Configuracion de TINT_SIS en archivo (plan PLAN_APP_TINT_SIS.md §5.1).

Los defaults son exactamente los valores que hoy viven en el codigo (rutas de la
CLI, `ENABLED_GRUPOS`, convencion de nombres). Si existe un `config.json` sus
claves pisan a los defaults; lo que no este en el archivo usa el default.

Ubicacion del archivo:
  - `%LOCALAPPDATA%\\TINT_SIS\\config.json` en Windows,
  - `~/.config/tint_sis/config.json` en el resto,
  o la que se pase explicitamente a `load_config` / `save_config`.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.adapters.homologos_filter import ENABLED_GRUPOS as _DEFAULT_ENABLED
from tint_sis.routing import EXPERT_MASTER_GLOB as _DEFAULT_EXPERT_GLOB
from tint_sis.routing import HOMOLOGOS_MASTER_NAME as _DEFAULT_HOMOLOGOS_NAME

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATA = _REPO_ROOT / "data"


def default_config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "TINT_SIS" / "config.json"
    return Path.home() / ".config" / "tint_sis" / "config.json"


@dataclass
class AppConfig:
    input_dir: Path = _DEFAULT_DATA / "input"
    # Carpeta base de salida. Los finales se guardan por software dentro de ella:
    # <output_dir>/xData/<grupo>_ready.{csv,xlsx}, <output_dir>/SANTINT/..., etc.
    output_dir: Path = _DEFAULT_DATA / "output"
    db_path: Path = _DEFAULT_DATA / "tint_sis.db"
    enabled_grupos: set[str] = field(default_factory=lambda: set(_DEFAULT_ENABLED))
    homologos_master_name: str = _DEFAULT_HOMOLOGOS_NAME
    expert_glob: str = _DEFAULT_EXPERT_GLOB
    # carpeta de entrega por software o por grupo/tienda: {"MP14": r"D:\\entrega\\mp14"}
    delivery_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "db_path": str(self.db_path),
            "enabled_grupos": sorted(self.enabled_grupos),
            "homologos_master_name": self.homologos_master_name,
            "expert_glob": self.expert_glob,
            "delivery_paths": dict(self.delivery_paths),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        base = cls()
        return cls(
            input_dir=Path(data.get("input_dir", base.input_dir)),
            output_dir=Path(data.get("output_dir", base.output_dir)),
            db_path=Path(data.get("db_path", base.db_path)),
            enabled_grupos=set(data.get("enabled_grupos", base.enabled_grupos)),
            homologos_master_name=data.get("homologos_master_name", base.homologos_master_name),
            expert_glob=data.get("expert_glob", base.expert_glob),
            delivery_paths=dict(data.get("delivery_paths", base.delivery_paths)),
        )


def load_config(path: Path | None = None) -> AppConfig:
    path = Path(path) if path else default_config_path()
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppConfig()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    path = Path(path) if path else default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path
