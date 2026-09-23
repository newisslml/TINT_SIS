"""Rutas HTTP que consume la UI, cableadas al motor real de `tint_sis`."""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from tint_sis.adapters import homologos_editor
from tint_sis.adapters.homologos_editor import HomologosEditor
from tint_sis.adapters.homologos_filter import read_expert_ids
from tint_sis.config import AppConfig, load_config, save_config
from tint_sis.db import repository
from tint_sis.db.database import get_session
from tint_sis.preview import preview_batch
from tint_sis.routing import EXPERT_MASTER_GLOB, find_homologos_master_pair

from . import _runner

router = APIRouter()

# Editor de homologos_TINT.xlsx: se abre una vez (carga pesada, ~decenas de
# segundos con el archivo real) y se mantiene en memoria entre pedidos hasta
# que la UI pide guardar. Un solo usuario/proceso, asi que un estado a nivel
# de modulo alcanza (mismo patron que `_runner` para la corrida del filtro).
_editor: HomologosEditor | None = None
_editor_path: Path | None = None

# read_expert_ids() lee el experto entero (~180k filas, ~50s medido con el
# archivo real) para calcular la cobertura. Sin cache, cada GET a una tienda
# -incluido el refresco despues de cada edicion- pagaba ese costo de nuevo;
# se cachea por archivo+mtime (se invalida sola si cambia el experto activo).
_expert_ids_cache: dict[Path, tuple[float, set[str]]] = {}


def _cached_expert_ids(path: Path) -> set[str]:
    mtime = path.stat().st_mtime
    cached = _expert_ids_cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    ids = read_expert_ids(path)
    _expert_ids_cache[path] = (mtime, ids)
    return ids


def _homologos_path(cfg: AppConfig) -> Path:
    return Path(cfg.input_dir) / cfg.homologos_master_name


def _get_editor() -> HomologosEditor:
    global _editor, _editor_path
    cfg = _cfg()
    path = _homologos_path(cfg)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No se encontro {path.name} en la carpeta de entrada")
    if _editor is None or _editor_path != path:
        try:
            _editor = HomologosEditor(path)
        except Exception as exc:  # noqa: BLE001 - se traduce a error de API
            raise HTTPException(status_code=500, detail=f"No se pudo abrir {path.name}: {exc}") from exc
        _editor_path = path
    return _editor


def _cfg() -> AppConfig:
    return load_config()


def _fmt_dt(dt) -> str:
    """Formatea una fecha de la DB en hora local. `creado_en` / `generado_en` se
    guardan en UTC (y vuelven naive tras el round-trip por SQLite), así que se les
    asigna UTC y se convierte a la zona local del equipo antes de mostrar."""
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


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


# Carpetas donde el flujo anterior (un solo experto xData) dejaba los archivos.
_CARPETAS_FLUJO_ANTERIOR = ("xData", "Tiendas filtradas")


def _salida_de_registro(reg, filtrados_dirname: str) -> tuple[str, dict, int]:
    """(software, fila para la UI, filas contadas) de un archivo generado. El
    software es la carpeta del archivo (<salida>/Archivos filtrados/<Software>/);
    los ciclos anteriores a la salida por software quedaban sueltos en la carpeta
    de filtrados (xData/ y despues Tiendas filtradas/). Las filas solo se cuentan
    para los .csv (contar un .xlsx obliga a abrirlo)."""
    ruta = Path(reg.ruta)
    software = ruta.parent.name
    if software in (filtrados_dirname, *_CARPETAS_FLUJO_ANTERIOR):
        software = "Flujo anterior (xData)"
    existe = ruta.exists()
    tipo = ruta.suffix.lower() or (".csv" if reg.adaptador.endswith("csv") else ".xlsx")
    filas = _count_data_rows(ruta) if tipo == ".csv" and existe else 0
    salida = {
        "salida": ruta.name,
        "tienda": reg.linea_producto,
        "tipo": tipo,
        "filas": _fmt_int(filas) if filas else "-",
        "existe": existe,
        "ruta": str(ruta),
    }
    return software, salida, filas


def _last_batch_files(cfg: AppConfig):
    """(fecha, grupos_dict, n_archivos, filas_totales) del ultimo batch en la DB,
    o None si no hay ninguno. `grupos` va por software."""
    session = get_session(cfg.db_path)
    try:
        batch = repository.get_last_batch(session)
        if batch is None:
            return None
        registros = repository.files_for_batch(session, batch)
        grupos: dict[str, list[dict]] = {}
        filas_totales = 0
        for reg in registros:
            software, salida, filas = _salida_de_registro(reg, cfg.filtrados_dirname)
            filas_totales += filas
            grupos.setdefault(software, []).append(salida)
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
    softwares = [s.nombre for s in cfg.softwares_activos()]
    return {
        "carpeta_trabajo": str(Path(cfg.input_dir).parent),
        "ultimo_ciclo": last["fecha"] if last else "sin ciclos",
        "software": ", ".join(softwares) or "-",
    }


@router.get("/inicio")
def get_inicio() -> dict:
    cfg = _cfg()
    last = _last_batch_files(cfg)
    prev = preview_batch(cfg)

    alertas = []
    for b in prev.bloqueantes + prev.advertencias:
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
            "experto": " · ".join(e.archivo for e in prev.expertos if e.archivo)
            or "(sin expertos en la carpeta)",
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
        "grupos": [{"titulo": software, "salidas": s} for software, s in last["grupos"].items()],
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
                software, salida, filas = _salida_de_registro(reg, cfg.filtrados_dirname)
                ruta = Path(reg.ruta)
                if salida["existe"]:
                    disponibles += 1
                    if carpeta_viva is None:
                        carpeta_viva = _carpeta_ciclo(ruta, cfg.filtrados_dirname)
                filas_totales += filas
                carpeta_reg = _carpeta_ciclo(ruta, cfg.filtrados_dirname)
                if carpeta_reg not in carpetas:
                    carpetas.append(carpeta_reg)
                grupos.setdefault(software, []).append(salida)
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
                    "grupos": [{"titulo": software, "salidas": s} for software, s in grupos.items()],
                }
            )
        return {"ciclos": ciclos}
    finally:
        session.close()


def _carpeta_ciclo(ruta: Path, filtrados_dirname: str) -> Path:
    """Carpeta que agrupa todas las salidas de un ciclo: la de los filtrados
    (padre de las carpetas por software). Para registros viejos (antes de la
    salida por software) es la carpeta del propio archivo."""
    return ruta.parent.parent if ruta.parent.parent.name == filtrados_dirname else ruta.parent


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


# --------------------------------------------------------------------------- #
# homologos (editor)
# --------------------------------------------------------------------------- #
def _homologo_sheet_to_dict(sheet) -> dict:
    return {
        "titulo": sheet.titulo,
        "filas_no_reconocidas": sheet.filas_no_reconocidas,
        "lineas": [
            {
                "nombre": linea.nombre,
                "path": linea.path,
                "pendiente": linea.pendiente,
                "homologos": [
                    {
                        "nombre": h.nombre,
                        "path": h.path,
                        "nota": h.nota,
                        "pendiente": h.pendiente,
                        "ids": h.ids,
                    }
                    for h in linea.homologos
                ],
            }
            for linea in sheet.lineas
        ],
    }


@router.get("/homologos/tiendas")
def get_homologos_tiendas() -> dict:
    cfg = _cfg()
    path = _homologos_path(cfg)
    if not path.exists():
        return {"tiendas": [], "existe": False}
    return {"tiendas": homologos_editor.list_sheet_names(path), "existe": True}


@router.get("/homologos/{tienda}")
def get_homologos_tienda(tienda: str) -> dict:
    editor = _get_editor()
    if tienda not in editor.tiendas():
        raise HTTPException(status_code=404, detail=f"La hoja '{tienda}' no existe en {editor.path.name}")
    sheet = editor.arbol(tienda)

    cfg = _cfg()
    par = find_homologos_master_pair(
        Path(cfg.input_dir), master_name=cfg.homologos_master_name, expert_glob=EXPERT_MASTER_GLOB
    )
    cobertura = None
    experto_usado = None
    if par is not None:
        try:
            expert_ids = _cached_expert_ids(par.expert_path)
            cobertura = homologos_editor.compute_cobertura(sheet, expert_ids)
            experto_usado = par.expert_path.name
        except (OSError, KeyError, ValueError):
            cobertura = None

    data = _homologo_sheet_to_dict(sheet)
    data["cobertura"] = cobertura
    data["experto_usado"] = experto_usado
    data["cambios_sin_guardar"] = editor.dirty
    return data


@router.post("/homologos/{tienda}/ids")
def post_homologos_id(tienda: str, payload: dict) -> dict:
    editor = _get_editor()
    try:
        editor.agregar_id(tienda, payload.get("linea"), payload.get("homologo"), payload.get("id_tint"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "cambios_sin_guardar": editor.dirty}


@router.delete("/homologos/{tienda}/ids")
def delete_homologos_id(tienda: str, payload: dict) -> dict:
    editor = _get_editor()
    try:
        editor.quitar_id(tienda, payload.get("linea"), payload.get("homologo"), payload.get("id_tint"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "cambios_sin_guardar": editor.dirty}


@router.post("/homologos/{tienda}/homologos")
def post_homologos_homologo(tienda: str, payload: dict) -> dict:
    editor = _get_editor()
    try:
        editor.agregar_homologo(tienda, payload.get("linea"), payload.get("nombre"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "cambios_sin_guardar": editor.dirty}


@router.post("/homologos/{tienda}/lineas")
def post_homologos_linea(tienda: str, payload: dict) -> dict:
    editor = _get_editor()
    try:
        editor.agregar_linea(tienda, payload.get("nombre"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "cambios_sin_guardar": editor.dirty}


@router.post("/homologos/guardar")
def post_homologos_guardar() -> dict:
    editor = _get_editor()
    try:
        backup = editor.guardar()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar: {exc}") from exc
    return {"guardado": True, "backup": str(backup)}
