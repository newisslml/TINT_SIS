"""Estado de la preparacion del experto (vista "Preparar experto").

Igual que `_runner` para el ciclo: 1 usuario / 1 PC, como mucho un trabajo a la
vez en un hilo aparte, y la UI consulta el estado por polling en
`/api/preparar/estado`. El trabajo tiene dos pasos que el usuario dispara por
separado: analizar el maestro (~1 min, no escribe nada) y, tras revisar el
resumen y decidir tiendas/nombres de los productos nuevos, preparar los
expertos (~2 min). El analisis queda en memoria para el segundo paso.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.adapters.sheet_filter import FormatoExpertoError
from tint_sis.config import AppConfig
from tint_sis.preparar import (
    Analisis,
    DecisionNuevo,
    PreparacionError,
    analizar_maestro,
    preparar_expertos,
)

from . import _avisos


@dataclass
class PrepState:
    # idle | analizando | analizado | preparando | listo | error
    estado: str = "idle"
    maestro: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    progreso: int = 0
    etapa: str = ""
    log: list[str] = field(default_factory=list)
    analisis: Analisis | None = None
    resultado: dict | None = None
    error: str | None = None

    def snapshot(self) -> dict:
        fin = self.finished_at or time.time()
        return {
            "estado": self.estado,
            "maestro": self.maestro,
            "progreso": self.progreso,
            "etapa": self.etapa,
            "transcurrido_seg": int(fin - self.started_at) if self.started_at else 0,
            "log": list(self.log),
            "analisis": self.analisis.to_dict() if self.analisis else None,
            "resultado": self.resultado,
            "error": self.error,
        }


_state = PrepState()
_lock = threading.Lock()


def snapshot() -> dict:
    with _lock:
        return _state.snapshot()


def ocupado() -> bool:
    return _state.estado in ("analizando", "preparando")


def _on_progress(evento: dict) -> None:
    with _lock:
        pct = evento.get("pct")
        if pct is not None:
            _state.progreso = max(_state.progreso, int(pct))
        etapa = str(evento.get("etapa") or "")
        if etapa:
            _state.etapa = etapa
            if evento.get("fase") == "etapa" and (not _state.log or _state.log[-1] != etapa):
                _state.log.append(etapa)


def _expertos_sin_generar(analisis: Analisis, cfg: AppConfig) -> list[str]:
    """"Experto 2 (Tinwise_Lab)" por cada experto que la preparacion no genera
    (no hay un experto anterior que sirva de plantilla)."""
    out = []
    for plan in analisis.expertos:
        if plan.estado == "ok":
            continue
        softwares = [s.nombre for s in cfg.software_defs() if s.experto == plan.label]
        out.append(f"{plan.label} ({', '.join(softwares)})" if softwares else plan.label)
    return out


def _avisar_expertos_sin_generar(faltan: list[str], cfg: AppConfig) -> None:
    _avisos.avisar(
        "Falta un experto" if len(faltan) == 1 else f"Faltan {len(faltan)} expertos",
        f"No se genera {', '.join(faltan)}: no hay un experto anterior en la carpeta de entrada que sirva de "
        "plantilla. Sus softwares van a quedar afuera del ciclo.",
        nivel="advertencia",
        vista="nuevo-ciclo",
        sistema=cfg.notificaciones,
    )


def _iniciar(estado: str, mensaje: str) -> bool:
    with _lock:
        if _state.estado in ("analizando", "preparando"):
            return False
        _state.estado = estado
        _state.started_at = time.time()
        _state.finished_at = None
        _state.progreso = 0
        _state.etapa = mensaje
        _state.log = [mensaje]
        _state.error = None
        return True


def _fallar(exc: BaseException, esperado: bool) -> None:
    with _lock:
        _state.estado = "error"
        _state.finished_at = time.time()
        # errores esperables (archivo abierto, formato) sin traceback
        _state.error = str(exc) if esperado else traceback.format_exc()
        _state.log.append("ERROR: " + (str(exc) if esperado else "falló (ver detalle)"))


def iniciar_analisis(cfg: AppConfig, maestro: Path) -> bool:
    """Analiza `maestro` en segundo plano. False si ya hay un trabajo en curso."""
    if not _iniciar("analizando", f"Analizando {Path(maestro).name}"):
        return False
    with _lock:
        _state.maestro = Path(maestro).name
        _state.analisis = None
        _state.resultado = None

    def correr() -> None:
        nombre = Path(maestro).name
        try:
            analisis = analizar_maestro(Path(maestro), cfg, on_progress=_on_progress)
        except (FormatoExpertoError, PreparacionError, OSError) as exc:
            _fallar(exc, esperado=True)
            _avisos.avisar("No se pudo analizar el maestro", f"{nombre}: {exc}", nivel="error",
                           vista="nuevo-ciclo", sistema=cfg.notificaciones)
            return
        except Exception as exc:  # noqa: BLE001 - se muestra el error crudo en la UI
            _fallar(exc, esperado=False)
            _avisos.avisar("No se pudo analizar el maestro", f"{nombre}: ver el detalle en Nuevo ciclo.",
                           nivel="error", vista="nuevo-ciclo", sistema=cfg.notificaciones)
            return
        with _lock:
            _state.estado = "analizado"
            _state.finished_at = time.time()
            _state.progreso = 100
            _state.analisis = analisis
            _state.log.append(
                f"Análisis listo: {len(analisis.nuevos)} producto(s) nuevo(s), "
                f"{len(analisis.cambios)} con cambios, {len(analisis.quitados)} que ya no vienen"
            )
        # el usuario tiene que revisar y decidir antes de preparar
        siguiente = (
            "Revisá el resumen y prepará los expertos."
            if analisis.puede_preparar
            else "Hay algo que impide preparar: revisalo en Nuevo ciclo."
        )
        faltan = _expertos_sin_generar(analisis, cfg)
        _avisos.avisar(
            "Análisis del maestro listo",
            f"{nombre}: {len(analisis.nuevos)} producto(s) nuevo(s). {siguiente}",
            nivel="error" if not analisis.puede_preparar else ("advertencia" if faltan else "ok"),
            vista="nuevo-ciclo",
            sistema=cfg.notificaciones,
        )
        if faltan:
            _avisar_expertos_sin_generar(faltan, cfg)

    threading.Thread(target=correr, daemon=True).start()
    return True


def iniciar_preparacion(cfg: AppConfig, decisiones: dict[str, DecisionNuevo]) -> str | None:
    """Prepara los expertos con el analisis en memoria. Devuelve None si arranco,
    o el motivo por el que no."""
    with _lock:
        analisis = _state.analisis
        estado = _state.estado
    if estado in ("analizando", "preparando"):
        return "Ya hay un trabajo en curso"
    if analisis is None or estado != "analizado":
        return "Primero hay que cargar y analizar el archivo maestro"
    if not analisis.puede_preparar:
        return "; ".join(analisis.bloqueantes)
    if not _iniciar("preparando", "Preparando los expertos"):
        return "Ya hay un trabajo en curso"

    def correr() -> None:
        try:
            resultado = preparar_expertos(analisis, cfg, decisiones, on_progress=_on_progress)
        except (PreparacionError, FormatoExpertoError) as exc:
            _fallar(exc, esperado=True)
            with _lock:
                # el analisis sigue valido: se puede corregir (cerrar el archivo) y reintentar
                _state.estado = "analizado"
                _state.finished_at = time.time()
            _avisos.avisar("No se pudieron preparar los expertos", str(exc), nivel="error",
                           vista="nuevo-ciclo", sistema=cfg.notificaciones)
            return
        except Exception as exc:  # noqa: BLE001
            _fallar(exc, esperado=False)
            _avisos.avisar("No se pudieron preparar los expertos", "Ver el detalle del error en Nuevo ciclo.",
                           nivel="error", vista="nuevo-ciclo", sistema=cfg.notificaciones)
            return
        with _lock:
            _state.estado = "listo"
            _state.finished_at = time.time()
            _state.progreso = 100
            _state.resultado = resultado.to_dict()
            _state.log.append(f"Expertos preparados: {', '.join(a.archivo for a in resultado.archivos)}")
        faltan = _expertos_sin_generar(analisis, cfg)
        _avisos.avisar(
            "Expertos preparados",
            f"{', '.join(a.archivo for a in resultado.archivos)} listos en la carpeta de entrada. "
            "Ya se puede ejecutar el ciclo.",
            nivel="advertencia" if faltan else "ok",
            vista="nuevo-ciclo",
            sistema=cfg.notificaciones,
        )
        if faltan:
            _avisar_expertos_sin_generar(faltan, cfg)

    threading.Thread(target=correr, daemon=True).start()
    return None


def reiniciar() -> None:
    """Vuelve a "idle" (para cargar otro maestro). No corta un trabajo en curso."""
    with _lock:
        if _state.estado in ("analizando", "preparando"):
            return
        _state.estado = "idle"
        _state.maestro = None
        _state.analisis = None
        _state.resultado = None
        _state.error = None
        _state.log = []
        _state.progreso = 0
        _state.etapa = ""
        _state.started_at = _state.finished_at = None
