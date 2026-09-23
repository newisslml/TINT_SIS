"""Estado de la corrida en curso.

1 usuario / 1 PC: hay como mucho UNA corrida a la vez. El pipeline se ejecuta en
un hilo aparte; `on_progress` actualiza este estado y la UI lo consulta por
polling en `/api/run/current`. Hay un renglon de progreso por archivo experto
(cada experto se lee una vez y genera los archivos de todas sus tiendas).

Cancelacion cooperativa: `request_cancel()` levanta una bandera; el callback
`on_progress` (que el motor invoca muy seguido: cada 2000 filas y por experto) la
chequea y lanza `RunCancelled`, que sube por el pipeline sin commitear la corrida.
La unica ventana sin chequeo es el armado de los libros filtrados de un experto
(comprimir el xlsx de cada tienda), que tarda segundos.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.config import AppConfig
from tint_sis.pipeline import run_pipeline


class RunCancelled(Exception):
    """El usuario pidio cancelar; se propaga desde on_progress hasta _run."""


@dataclass
class RunState:
    estado: str = "idle"  # idle | en_curso | ok | error
    started_at: float | None = None
    finished_at: float | None = None
    total_expertos: int = 0
    expertos: dict[str, int] = field(default_factory=dict)  # experto -> % (0..100)
    expertos_txt: dict[str, str] = field(default_factory=dict)  # experto -> etapa legible
    expertos_seen: dict[str, float] = field(default_factory=dict)  # experto -> ts del ultimo evento
    expertos_cap: dict[str, int] = field(default_factory=dict)  # experto -> techo de creep de la etapa
    log_buckets: dict[str, int] = field(default_factory=dict)  # experto -> ultimo 25% logueado
    log: list[str] = field(default_factory=list)
    error: str | None = None
    summary: dict | None = None  # resultados-shaped, listo para /api/resultados

    def _expertos_view(self, now: float) -> list[dict]:
        # Entre eventos (armado de los libros filtrados, que no tiene hook) la
        # barra de un experto no debe quedar congelada: se la deja avanzar
        # despacio hasta el techo de su etapa.
        out = []
        for experto, pct in self.expertos.items():
            if 0 < pct < 100:
                stale = now - self.expertos_seen.get(experto, now)
                if stale > 2:
                    cap = self.expertos_cap.get(experto, pct)
                    pct = min(cap, pct + int(stale / 3))
            out.append({"experto": experto, "progreso": pct, "texto": self.expertos_txt.get(experto, "")})
        return out

    def snapshot(self) -> dict:
        now = time.time()
        ahora = self.finished_at or now
        elapsed = int(ahora - self.started_at) if self.started_at else 0
        tv = self._expertos_view(now)
        pcts = [t["progreso"] for t in tv]
        # el promedio se hace sobre el total de expertos del ciclo, no sobre los
        # que ya arrancaron, para que la barra global no salte de golpe.
        divisor = max(self.total_expertos, len(pcts), 1)
        global_pct = int(sum(pcts) / divisor) if pcts else 0
        if self.estado == "ok":
            global_pct = 100
        return {
            "estado": self.estado,
            "progreso_global": global_pct,
            "transcurrido_seg": elapsed,
            "expertos": tv,
            "log": list(self.log),
            "error": self.error,
        }


_state = RunState()
_lock = threading.Lock()
_cancel = threading.Event()
_thread: threading.Thread | None = None


def is_running() -> bool:
    return _state.estado == "en_curso"


def request_cancel() -> bool:
    """Marca la corrida en curso para cancelar. Devuelve False si no hay ninguna."""
    with _lock:
        if _state.estado != "en_curso":
            return False
        _cancel.set()
        _state.log.append("Cancelando… (se corta al terminar el paso en curso)")
        return True


def snapshot() -> dict:
    with _lock:
        return _state.snapshot()


def last_summary() -> dict | None:
    with _lock:
        return _state.summary


def start(config: AppConfig) -> bool:
    """Arranca una corrida. Devuelve False si ya hay una en curso."""
    global _thread
    with _lock:
        if _state.estado == "en_curso":
            return False
        _reset_locked()
        _state.estado = "en_curso"
        _state.started_at = time.time()
        _state.log.append("Iniciando ciclo - filtro por productos de cada experto")

    _thread = threading.Thread(target=_run, args=(config,), daemon=True)
    _thread.start()
    return True


def _reset_locked() -> None:
    _cancel.clear()
    _state.estado = "idle"
    _state.started_at = None
    _state.finished_at = None
    _state.total_expertos = 0
    _state.expertos = {}
    _state.expertos_txt = {}
    _state.expertos_seen = {}
    _state.expertos_cap = {}
    _state.log_buckets = {}
    _state.log = []
    _state.error = None
    _state.summary = None


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _on_progress(event: dict) -> None:
    if _cancel.is_set():
        raise RunCancelled()
    fase = event.get("fase")
    with _lock:
        if fase == "inicio":
            _state.total_expertos = int(event.get("total") or 0)
        elif fase == "experto_inicio":
            experto = str(event.get("item"))
            _state.expertos[experto] = 2
            _state.expertos_txt[experto] = "arrancando…"
            _state.expertos_seen[experto] = time.time()
            _state.expertos_cap[experto] = 10
            _state.log.append(str(event.get("mensaje") or f"Filtrando {experto}"))
        elif fase == "experto_progreso":
            _apply_experto_progreso(event)
        elif fase == "experto_ok":
            experto = str(event.get("item"))
            _state.expertos[experto] = 100
            _state.expertos_txt[experto] = "listo"
            _state.expertos_seen[experto] = time.time()
            _state.log.append(str(event.get("mensaje") or f"{experto} listo"))
        elif fase == "fin":
            _state.log.append("Archivos entregados por software")
        elif fase == "mensaje":
            # aviso suelto (p.ej. el CSV de un software), va directo al log
            _state.log.append(str(event.get("mensaje") or ""))


# Reparto del % de cada experto entre sus sub-etapas:
#   leer el experto y repartir filas por tienda  ~2..50   (progreso fino)
#   armar el libro filtrado de cada tienda       ~50..70  (sin hook: creep + franjas)
#   escribir los CSV (solo softwares en CSV)     ~70..99  (progreso fino por archivo)
_ETAPA_RANGO = {"filtrar": (2, 50), "guardar": (50, 70), "csv": (70, 99)}


def _apply_experto_progreso(event: dict) -> None:
    experto = str(event.get("item"))
    etapa = str(event.get("etapa") or "filtrar")
    leidas = int(event.get("leidas") or 0)
    sub_total = int(event.get("sub_total") or 0)
    frac = min(1.0, max(0.0, leidas / sub_total)) if sub_total else 0.0

    lo, hi = _ETAPA_RANGO.get(etapa, (2, 30))
    _state.expertos_seen[experto] = time.time()
    _state.expertos_cap[experto] = hi

    if etapa == "guardar":
        pct = lo
        _state.expertos_txt[experto] = "guardando Excel filtrado por tienda…"
    elif etapa == "csv":
        pct = lo + int(frac * (hi - lo))
        _state.expertos_txt[experto] = f"escribiendo CSV  {_miles(leidas)}" + (
            f" / {_miles(sub_total)}" if sub_total else ""
        )
    else:  # filtrar
        pct = lo + int(frac * (hi - lo))
        _state.expertos_txt[experto] = f"filtrando experto  {_miles(leidas)}" + (
            f" / {_miles(sub_total)}" if sub_total else ""
        )
        if sub_total:
            bucket = int(frac * 4)  # log al cruzar cada 25 %
            if bucket > _state.log_buckets.get(experto, -1):
                _state.log_buckets[experto] = bucket
                _state.log.append(f"{experto}: {_miles(leidas)} / {_miles(sub_total)} filas")

    _state.expertos[experto] = max(_state.expertos.get(experto, 0), pct)


def _run(config: AppConfig) -> None:
    try:
        summary = run_pipeline(
            input_dir=Path(config.input_dir),
            output_dir=Path(config.output_dir),
            db_path=Path(config.db_path),
            enabled_grupos=set(config.enabled_grupos),
            expertos_habilitados=set(config.expertos_habilitados),
            productos_name=config.productos_name,
            expertos_globs=config.expertos,
            softwares=config.software_defs(),
            filtrados_dirname=config.filtrados_dirname,
            on_progress=_on_progress,
        )
    except RunCancelled:
        with _lock:
            _state.estado = "cancelado"
            _state.finished_at = time.time()
            for e, p in list(_state.expertos.items()):
                if 0 < p < 100:
                    _state.expertos_txt[e] = "cancelado"
            _state.log.append(
                "Ciclo cancelado por el usuario. Los softwares de los expertos que ya "
                "habían terminado quedaron escritos; el resto no se generó."
            )
        return
    except Exception:  # noqa: BLE001 - se muestra el error crudo en la UI
        with _lock:
            _state.estado = "error"
            _state.finished_at = time.time()
            _state.error = traceback.format_exc()
            _state.log.append("ERROR: la corrida fallo (ver detalle)")
        return

    grupos: dict[str, list[dict]] = {}
    for gf in summary.archivos:
        grupos.setdefault(gf.software, []).append(
            {
                "salida": Path(gf.ruta).name,
                "tienda": gf.grupo,
                "tipo": gf.tipo,
                "filas": f"{gf.filas:,}".replace(",", "."),
                "existe": Path(gf.ruta).exists(),
                "ruta": str(gf.ruta),
            }
        )
    filas_totales = sum(gf.filas for gf in summary.archivos)

    with _lock:
        _state.estado = "ok"
        _state.finished_at = time.time()
        _state.summary = {
            "resumen": {
                "archivos": len(summary.archivos),
                "filas_totales": f"{filas_totales:,}".replace(",", "."),
                "advertencias": len(summary.ingestion_warnings),
            },
            "grupos": [{"titulo": software, "salidas": s} for software, s in grupos.items()],
            "advertencias": list(summary.ingestion_warnings),
        }
        _state.log.append(f"Ciclo terminado. {len(summary.archivos)} archivos generados.")
