"""Rutas HTTP que consume la UI, cableadas al motor real de `tint_sis`."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from tint_sis.config import AppConfig, load_config, save_config
from tint_sis.db import repository
from tint_sis.db.database import get_session
from tint_sis.preview import preview_batch

from . import _runner

router = APIRouter()


def _cfg() -> AppConfig:
    return load_config()


def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _count_data_rows(path: Path) -> int:
    """Cuenta filas de datos (sin encabezado) de un .csv ya generado."""
    try:
        with open(path, "rb") as fh:
            total = sum(1 for _ in fh)
        return max(0, total - 1)
    except OSError:
        return 0


def _last_batch_files(cfg: AppConfig):
    """(fecha, grupos_dict, n_archivos, filas_totales) del ultimo batch en la DB,
    o None si no hay ninguno."""
    session = get_session(cfg.db_path)
    try:
        batch = repository.get_last_batch(session)
        if batch is None:
            return None
        registros = repository.files_for_batch(session, batch)
        grupos: dict[str, list[dict]] = {}
        filas_totales = 0
        for reg in registros:
            ruta = Path(reg.ruta)
            tipo = ".csv" if reg.adaptador.endswith("csv") else ".xlsx"
            filas = _count_data_rows(ruta) if tipo == ".csv" and ruta.exists() else 0
            if tipo == ".csv":
                filas_totales += filas
            grupos.setdefault(reg.linea_producto, []).append(
                {
                    "salida": ruta.name,
                    "tipo": tipo,
                    "filas": _fmt_int(filas) if filas else "-",
                    "existe": ruta.exists(),
                }
            )
        return {
            "fecha": _fmt_dt(batch.creado_en),
            "grupos": grupos,
            "n_archivos": len(registros),
            "filas_totales": _fmt_int(filas_totales),
        }
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# rutas
# --------------------------------------------------------------------------- #
@router.get("/estado")
def get_estado() -> dict:
    cfg = _cfg()
    last = _last_batch_files(cfg)
    return {
        "carpeta_trabajo": str(Path(cfg.input_dir).parent),
        "ultimo_ciclo": last["fecha"] if last else "sin ciclos",
        "software": "xData",
    }


@router.get("/inicio")
def get_inicio() -> dict:
    cfg = _cfg()
    last = _last_batch_files(cfg)
    prev = preview_batch(cfg)

    alertas = []
    for b in prev.bloqueantes:
        alertas.append({"nivel": "advertencia", "texto": b})
    if not cfg.delivery_paths:
        alertas.append(
            {
                "nivel": "info",
                "texto": "No hay carpeta de entrega configurada. Se puede generar igual; "
                "habra que copiar la GData a los tecnicos a mano.",
            }
        )

    mem = _runner.last_summary()
    advertencias = (
        mem["resumen"]["advertencias"] if mem else (0 if last is None else "-")
    )

    return {
        "ultimo_ciclo": {
            "fecha": last["fecha"] if last else "-",
            "experto": prev.experto_activo or "(sin experto en la carpeta)",
            "archivos_generados": last["n_archivos"] if last else 0,
            "advertencias": advertencias,
        },
        "alertas": alertas,
    }


@router.get("/preview")
def get_preview() -> dict:
    return preview_batch(_cfg()).to_dict()


@router.post("/run")
def post_run() -> dict:
    cfg = _cfg()
    prev = preview_batch(cfg)
    if not prev.puede_ejecutar:
        raise HTTPException(status_code=409, detail="; ".join(prev.bloqueantes) or "No se puede ejecutar")
    if not _runner.start(cfg):
        raise HTTPException(status_code=409, detail="Ya hay una corrida en curso")
    return _runner.snapshot()


@router.get("/run/current")
def get_run_current() -> dict:
    return _runner.snapshot()


@router.post("/run/cancel")
def post_run_cancel() -> dict:
    _runner.request_cancel()
    return _runner.snapshot()


@router.get("/resultados")
def get_resultados() -> dict:
    mem = _runner.last_summary()
    if mem is not None:
        return mem

    cfg = _cfg()
    last = _last_batch_files(cfg)
    if last is None:
        return {"resumen": {"archivos": 0, "filas_totales": "0", "advertencias": 0}, "grupos": [], "advertencias": []}
    return {
        "resumen": {
            "archivos": last["n_archivos"],
            "filas_totales": last["filas_totales"],
            "advertencias": "-",
        },
        "grupos": [
            {"titulo": f"xData -> {g}", "salidas": s} for g, s in last["grupos"].items()
        ],
        "advertencias": [],
    }


@router.get("/historial")
def get_historial() -> dict:
    """Lista los ciclos ejecutados (batches en la DB) con sus archivos generados,
    marcando cuáles siguen disponibles en disco para revisar el backup."""
    cfg = _cfg()
    session = get_session(cfg.db_path)
    try:
        ciclos = []
        for batch in repository.list_batches(session, limit=50):
            registros = repository.files_for_batch(session, batch)
            grupos: dict[str, list[dict]] = {}
            filas_totales = 0
            disponibles = 0
            carpetas: list[Path] = []
            carpeta_viva = None
            for reg in registros:
                ruta = Path(reg.ruta)
                existe = ruta.exists()
                tipo = ".csv" if reg.adaptador.endswith("csv") else ".xlsx"
                filas = _count_data_rows(ruta) if tipo == ".csv" and existe else 0
                if existe:
                    disponibles += 1
                    if carpeta_viva is None:
                        carpeta_viva = ruta.parent
                if tipo == ".csv":
                    filas_totales += filas
                if ruta.parent not in carpetas:
                    carpetas.append(ruta.parent)
                grupos.setdefault(reg.linea_producto, []).append(
                    {
                        "salida": ruta.name,
                        "tipo": tipo,
                        "filas": _fmt_int(filas) if filas else "-",
                        "existe": existe,
                        "ruta": str(ruta),
                    }
                )
            # carpeta local del backup: la del primer archivo que aún existe, o la
            # esperada (la del primer registro) si ninguno sigue en disco
            carpeta = carpeta_viva or (carpetas[0] if carpetas else None)
            ciclos.append(
                {
                    "id": batch.id,
                    "fecha": _fmt_dt(batch.creado_en),
                    "origen": batch.origen_dir,
                    "n_archivos": len(registros),
                    "n_disponibles": disponibles,
                    "filas_totales": _fmt_int(filas_totales),
                    "carpeta": str(carpeta) if carpeta else None,
                    "carpeta_existe": bool(carpeta and carpeta.is_dir()),
                    "grupos": [
                        {"titulo": f"xData → {g}", "salidas": s} for g, s in grupos.items()
                    ],
                }
            )
        return {"ciclos": ciclos}
    finally:
        session.close()


def _reveal_roots(cfg: AppConfig) -> list[Path]:
    """Carpetas bajo las que se permite abrir algo desde la UI: la salida
    configurada y la carpeta de trabajo (donde viven backups de ciclos viejos)."""
    roots = []
    for candidato in (Path(cfg.output_dir), Path(cfg.input_dir).parent):
        try:
            resuelto = candidato.resolve()
        except OSError:
            continue
        if resuelto not in roots:
            roots.append(resuelto)
    return roots


@router.post("/reveal")
def post_reveal(payload: dict) -> dict:
    """Abre en el explorador un archivo generado por un ciclo, o la carpeta que lo
    contiene. Sólo se permiten rutas dentro de la carpeta de salida o de trabajo."""
    raw = (payload or {}).get("ruta", "")
    modo = (payload or {}).get("modo", "carpeta")
    if not raw:
        raise HTTPException(status_code=400, detail="Falta 'ruta'")

    cfg = _cfg()
    try:
        objetivo = Path(raw).resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Ruta inválida") from exc
    if not any(objetivo == r or r in objetivo.parents for r in _reveal_roots(cfg)):
        raise HTTPException(status_code=400, detail="Ruta fuera de la carpeta de trabajo")

    if objetivo.is_dir():
        destino = objetivo
    elif modo == "archivo" and objetivo.is_file():
        destino = objetivo
    else:
        destino = objetivo.parent
    if not destino.exists():
        raise HTTPException(status_code=404, detail=f"Ya no existe en disco: {destino}")
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(destino))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(destino)])
        else:
            subprocess.Popen(["xdg-open", str(destino)])
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir: {exc}") from exc
    return {"abierto": str(destino)}


@router.get("/config")
def get_config() -> dict:
    return _cfg().to_dict()


@router.put("/config")
def put_config(nuevo: dict) -> dict:
    actual = _cfg().to_dict()
    actual.update({k: v for k, v in nuevo.items() if k in actual})
    cfg = AppConfig.from_dict(actual)
    path = save_config(cfg)
    return {"guardado": True, "config": cfg.to_dict(), "archivo": str(path)}


@router.post("/input/open")
def post_input_open() -> dict:
    cfg = _cfg()
    carpeta = Path(cfg.input_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(carpeta))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir la carpeta: {exc}") from exc
    return {"abierto": str(carpeta)}


@router.post("/input/upload")
async def post_input_upload(file: UploadFile) -> dict:
    cfg = _cfg()
    carpeta = Path(cfg.input_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = Path(file.filename or "archivo.xlsx").name
    destino = carpeta / nombre
    data = await file.read()
    destino.write_bytes(data)
    return {"guardado": nombre, "preview": preview_batch(cfg).to_dict()}
