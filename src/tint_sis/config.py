"""Configuracion de TINT_SIS en archivo (plan PLAN_APP_TINT_SIS.md §5.1).

Los defaults son exactamente los valores que hoy viven en el codigo (rutas de la
CLI, `ENABLED_GRUPOS`, expertos y softwares de `expertos.py`). Si existe un
`config.json` sus claves pisan a los defaults; lo que no este en el archivo usa
el default.

Ubicacion del archivo:
  - `%LOCALAPPDATA%\\TINT_SIS\\config.json` en Windows,
  - `~/.config/tint_sis/config.json` en el resto,
  o la que se pase explicitamente a `load_config` / `save_config`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.expertos import (
    ENABLED_GRUPOS as _DEFAULT_ENABLED,
    EXPERTOS,
    FILTRADOS_DIRNAME,
    PRODUCTOS_NAME,
    SOFTWARES_DEFAULT,
    SoftwareDef,
)
from tint_sis.paths import app_data_dir, default_data_dir, default_db_path
from tint_sis.routing import HOMOLOGOS_MASTER_NAME as _DEFAULT_HOMOLOGOS_NAME

_DEFAULT_DATA = default_data_dir()


def default_config_path() -> Path:
    return app_data_dir() / "config.json"


def _default_expertos() -> dict[str, str]:
    return {label: d.default_glob for label, d in EXPERTOS.items()}


def _default_softwares() -> list[dict]:
    return [s.to_dict() for s in SOFTWARES_DEFAULT]


@dataclass
class AppConfig:
    input_dir: Path = _DEFAULT_DATA / "input"
    # Carpeta base de salida. Los finales se guardan por software dentro de ella:
    # <output_dir>/Archivos filtrados/<Software>/<tienda>_ready.<ext>
    output_dir: Path = _DEFAULT_DATA / "output"
    db_path: Path = default_db_path()
    enabled_grupos: set[str] = field(default_factory=lambda: set(_DEFAULT_ENABLED))
    # tabla de productos (que tiendas lleva cada producto, por experto)
    productos_name: str = PRODUCTOS_NAME
    # label del experto -> patron de nombre en la carpeta de entrada
    expertos: dict[str, str] = field(default_factory=_default_expertos)
    # expertos con los que se trabaja en el ciclo (los demas y sus softwares se omiten)
    expertos_habilitados: set[str] = field(default_factory=lambda: set(EXPERTOS))
    # a que software va cada experto, para que tiendas y en que formato
    softwares: list[dict] = field(default_factory=_default_softwares)
    filtrados_dirname: str = FILTRADOS_DIRNAME
    # homologos por ID (flujo anterior): solo lo usan el editor de homologos y
    # `cli productos-init` para armar la tabla de productos la primera vez
    homologos_master_name: str = _DEFAULT_HOMOLOGOS_NAME
    # carpeta de entrega por software o por grupo/tienda: {"MP14": r"D:\\entrega\\mp14"}
    delivery_paths: dict[str, str] = field(default_factory=dict)

    def software_defs(self) -> list[SoftwareDef]:
        return [SoftwareDef.from_dict(s) for s in self.softwares]

    def softwares_activos(self) -> list[SoftwareDef]:
        """Softwares que el ciclo genera: su experto habilitado y al menos una
        de sus tiendas habilitada."""
        return [
            s
            for s in self.software_defs()
            if s.experto in self.expertos_habilitados and any(t in self.enabled_grupos for t in s.tiendas)
        ]

    def to_dict(self) -> dict:
        return {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "db_path": str(self.db_path),
            "enabled_grupos": sorted(self.enabled_grupos),
            "productos_name": self.productos_name,
            "expertos": dict(self.expertos),
            "expertos_habilitados": [e for e in EXPERTOS if e in self.expertos_habilitados],
            "softwares": [dict(s) for s in self.softwares],
            "filtrados_dirname": self.filtrados_dirname,
            "homologos_master_name": self.homologos_master_name,
            "delivery_paths": dict(self.delivery_paths),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        base = cls()
        expertos = dict(base.expertos)
        expertos.update({k: str(v) for k, v in (data.get("expertos") or {}).items() if k in EXPERTOS})
        return cls(
            input_dir=Path(data.get("input_dir", base.input_dir)),
            output_dir=Path(data.get("output_dir", base.output_dir)),
            db_path=Path(data.get("db_path", base.db_path)),
            enabled_grupos=set(data.get("enabled_grupos", base.enabled_grupos)),
            productos_name=data.get("productos_name", base.productos_name),
            expertos=expertos,
            expertos_habilitados={
                e for e in data.get("expertos_habilitados", base.expertos_habilitados) if e in EXPERTOS
            },
            softwares=_softwares_validos(data.get("softwares"), base.softwares),
            filtrados_dirname=data.get("filtrados_dirname", base.filtrados_dirname),
            homologos_master_name=data.get("homologos_master_name", base.homologos_master_name),
            delivery_paths=dict(data.get("delivery_paths", base.delivery_paths)),
        )


def _softwares_validos(valor: object, default: list[dict]) -> list[dict]:
    """La lista de softwares del archivo si es valida entera; si no, el default
    (un config a medio editar no debe dejar la app sin softwares)."""
    if not isinstance(valor, list):
        return default
    try:
        defs = [SoftwareDef.from_dict(s) for s in valor]
    except (KeyError, TypeError, ValueError):
        return default
    if any(d.experto not in EXPERTOS for d in defs):
        return default
    return [d.to_dict() for d in defs]


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
