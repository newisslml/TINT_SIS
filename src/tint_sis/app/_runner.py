"""Estado de la corrida en curso.

1 usuario / 1 PC: hay como mucho UNA corrida a la vez. El pipeline (lento, 12-15
min) se ejecuta en un hilo aparte; `on_progress` actualiza este estado y la UI lo
consulta por polling en `/api/run/current`.

Cancelacion cooperativa: `request_cancel()` levanta una bandera; el callback
`on_progress` (que el motor invoca muy seguido: cada 2000 filas y por tienda) la
chequea y lanza `RunCancelled`, que sube por el pipeline sin commitear la corrida.
La unica ventana sin chequeo es el `.save()` del xlsx de una tienda (sin hook),
asi que cancelar ahi puede tardar hasta 1-2 min en soltar.
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
    total_tiendas: int = 0
    tiendas: dict[str, int] = field(default_factory=dict)  # grupo -> % (0..100)
    tiendas_txt: dict[str, str] = field(default_factory=dict)  # grupo -> etapa legible
    tiendas_seen: dict[str, float] = field(default_factory=dict)  # grupo -> ts del ultimo evento
    tiendas_cap: dict[str, int] = field(default_factory=dict)  # grupo -> techo de creep de la etapa
    log_buckets: dict[str, int] = field(default_factory=dict)  # grupo -> ultimo 25% logueado
    log: list[str] = field(default_factory=list)
    error: str | None = None
    summary: dict | None = None  # resultados-shaped, listo para /api/resultados

    def _tiendas_view(self, now: float) -> list[dict]:
        # Entre eventos (sobre todo durante el .save() del xlsx, que no tiene hook)
        # la barra de una tienda no debe quedar congelada: se la deja avanzar
        # despacio hasta el techo de su etapa.
        out = []
        for grupo, pct in self.tiendas.items():
            if 0 < pct < 100:
                stale = now - self.tiendas_seen.get(grupo, now)
                if stale > 2:
                    cap = self.tiendas_cap.get(grupo, pct)
                    pct = min(cap, pct + int(stale / 6))
            out.append({"grupo": grupo, "progreso": pct, "texto": self.tiendas_txt.get(grupo, "")})
        return out

    def snapshot(self) -> dict:
        now = time.time()
        ahora = self.finished_at or now
        elapsed = int(ahora - self.started_at) if self.started_at else 0
        tv = self._tiendas_view(now)
        pcts = [t["progreso"] for t in tv]
        # el promedio se hace sobre el total de tiendas del ciclo, no sobre las que
        # ya arrancaron, para que la barra global no salte de golpe.
        divisor = max(self.total_tiendas, len(pcts), 1)
        global_pct = int(sum(pcts) / divisor) if pcts else 0
        if self.estado == "ok":
            global_pct = 100
        return {
            "estado": self.estado,
            "progreso_global": global_pct,
            "transcurrido_seg": elapsed,
            "tiendas": tv,
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
        _state.log.append("Iniciando ciclo xData - filtro por homologos")

    _thread = threading.Thread(target=_run, args=(config,), daemon=True)
    _thread.start()
    return True


def _reset_locked() -> None:
    _cancel.clear()
    _state.estado = "idle"
    _state.started_at = None
    _state.finished_at = None
    _state.total_tiendas = 0
    _state.tiendas = {}
    _state.tiendas_txt = {}
    _state.tiendas_seen = {}
    _state.tiendas_cap = {}
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
        if fase == "inicio" and event.get("mensaje") == "Filtro por homologos":
            _state.total_tiendas = int(event.get("total") or 0)
        elif fase == "tienda_inicio":
            grupo = str(event.get("item"))
            _state.tiendas[grupo] = 2
            _state.tiendas_txt[grupo] = "arrancando…"
            _state.tiendas_seen[grupo] = time.time()
            _state.tiendas_cap[grupo] = 30
            _state.log.append(str(event.get("mensaje") or f"Filtrando {grupo}"))
        elif fase == "tienda_progreso":
            _apply_tienda_progreso(event)
        elif fase == "tienda_ok":
            grupo = str(event.get("item"))
            _state.tiendas[grupo] = 100
            _state.tiendas_txt[grupo] = "listo"
            _state.tiendas_seen[grupo] = time.time()
            _state.log.append(str(event.get("mensaje") or f"{grupo} listo"))
        elif fase == "fin":
            _state.log.append("Escribiendo _ready por tienda")


# Reparto del % de cada tienda entre sus 3 sub-etapas. El guardado del .xlsx
# (openpyxl write_only + number_format por celda, sin hook posible) es la etapa
# mas larga para las tiendas grandes, por eso se lleva el rango mayor: en esa
# ventana la barra avanza sola despacio (creep) hasta el techo, con texto claro.
#   leer+cruzar el experto     ~2..22   (progreso fino, ~20-30 s)
#   guardar el .xlsx filtrado  ~22..75  (creep + franjas en movimiento)
#   escribir el .csv           ~75..99  (progreso fino)
_ETAPA_RANGO = {"filtrar": (2, 22), "guardar_xlsx": (22, 75), "csv": (75, 99)}


def _apply_tienda_progreso(event: dict) -> None:
    grupo = str(event.get("item"))
    etapa = str(event.get("etapa") or "filtrar")
    leidas = int(event.get("leidas") or 0)
    sub_total = int(event.get("sub_total") or 0)
    frac = min(1.0, max(0.0, leidas / sub_total)) if sub_total else 0.0

    lo, hi = _ETAPA_RANGO.get(etapa, (2, 30))
    _state.tiendas_seen[grupo] = time.time()
    _state.tiendas_cap[grupo] = hi

    if etapa == "guardar_xlsx":
        pct = lo
        _state.tiendas_txt[grupo] = "guardando Excel filtrado…"
    elif etapa == "csv":
        pct = lo + int(frac * (hi - lo))
        _state.tiendas_txt[grupo] = f"escribiendo CSV  {_miles(leidas)}" + (
            f" / {_miles(sub_total)}" if sub_total else ""
        )
    else:  # filtrar
        pct = lo + int(frac * (hi - lo))
        _state.tiendas_txt[grupo] = f"filtrando experto  {_miles(leidas)}" + (
            f" / {_miles(sub_total)}" if sub_total else ""
        )
        if sub_total:
            bucket = int(frac * 4)  # log al cruzar cada 25 %
            if bucket > _state.log_buckets.get(grupo, -1):
                _state.log_buckets[grupo] = bucket
                _state.log.append(f"{grupo}: {_miles(leidas)} / {_miles(sub_total)} filas del experto")

    _state.tiendas[grupo] = max(_state.tiendas.get(grupo, 0), pct)


def _run(config: AppConfig) -> None:
    try:
        summary = run_pipeline(
            input_dir=Path(config.input_dir),
            output_dir=Path(config.output_dir),
            db_path=Path(config.db_path),
            enabled_grupos=set(config.enabled_grupos),
            homologos_master_name=config.homologos_master_name,
            expert_glob=config.expert_glob,
            on_progress=_on_progress,
        )
    except RunCancelled:
        with _lock:
            _state.estado = "cancelado"
            _state.finished_at = time.time()
            for g, p in list(_state.tiendas.items()):
                if 0 < p < 100:
                    _state.tiendas_txt[g] = "cancelado"
            _state.log.append(
                "Ciclo cancelado por el usuario. Las tiendas que ya habían terminado "
                "quedaron escritas; el resto no se generó."
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
        grupos.setdefault(gf.grupo, []).append(
            {"salida": Path(gf.ruta).name, "tipo": gf.tipo, "filas": f"{gf.filas:,}".replace(",", ".")}
        )
    filas_totales = sum(gf.filas for gf in summary.archivos if gf.tipo == ".csv")

    with _lock:
        _state.estado = "ok"
        _state.finished_at = time.time()
        _state.summary = {
            "resumen": {
                "archivos": len(summary.archivos),
                "filas_totales": f"{filas_totales:,}".replace(",", "."),
                "advertencias": len(summary.ingestion_warnings),
            },
            "grupos": [
                {"titulo": f"xData -> {g}", "salidas": s} for g, s in grupos.items()
            ],
            "advertencias": list(summary.ingestion_warnings),
        }
        _state.log.append(f"Ciclo terminado. {len(summary.archivos)} archivos generados.")
