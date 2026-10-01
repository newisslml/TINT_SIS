"""Tabla de productos (homologos_TINT.xlsx): que tiendas lleva cada producto y
como se llama ese producto en cada archivo experto.

Reemplaza al cruce por ID_TINT: en el listado por ID anterior
(homologos_TINT_legacy.xlsx) cada tienda toma
productos completos (ningun producto a medias) y cada homologo (SUBP####) es
exactamente un producto, asi que alcanza con una fila por producto. Los
expertos se cargan tal como llegan, sin IDs.

Hoja "Productos" (una fila por producto):

  SUBP | Línea | Producto | Experto 1 | Experto 2 | Experto 3 | MP14 | MP12 | Tiendas 14 | Tiendas 12 | Revisar

  - Experto N: nombre del producto en ese experto (Experto 1/2: columna
    "Producto"; Experto 3: "group_code / product_code"). Varios nombres se
    separan con ";". Se comparan sin acentos, mayusculas ni espacios.
  - Columnas de tienda: cualquier valor (x, si, 1) = la tienda lleva el
    producto. Toda columna que no sea fija ni de experto se toma como tienda.
  - Revisar / Notas: solo informativas, el sistema no las lee.

Un producto que esta en la tabla sin ninguna tienda marcada se considera
conocido y no se entrega; uno que un experto trae y no esta en la tabla se
avisa como "sin asignar" en cada ciclo (nunca se descarta en silencio).

`bootstrap_tabla` arma la primera version a partir de homologos_TINT_legacy.xlsx
(tiendas por producto), el xData_DATACOMPLETA con ID_TINT (nombre exacto en
Experto 3) y los catalogos de los expertos (nombres sugeridos en Experto 1/2,
marcados para revisar).
"""
from __future__ import annotations

import difflib
import os
import re
import shutil
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from tint_sis.adapters import homologos_editor
from tint_sis.adapters.sheet_filter import contar_claves
from tint_sis.expertos import EXPERTOS, KEY_SEP, normalizar

HOJA_PRODUCTOS = "Productos"
HOJA_SIN_ASIGNAR = "Sin asignar"
HOJA_LEEME = "Leeme"

COL_SUBP = "SUBP"
COL_LINEA = "Línea"
COL_PRODUCTO = "Producto"
COL_REVISAR = "Revisar"
COLUMNAS_FIJAS = (COL_SUBP, COL_LINEA, COL_PRODUCTO)
COLUMNAS_INFO = (COL_REVISAR, "Notas")
SEPARADOR_NOMBRES = ";"
MARCA = "x"
_NO_MARCA = {"", "0", "no", "-", "false", "falso"}


# --------------------------------------------------------------------------- #
# lectura
# --------------------------------------------------------------------------- #
@dataclass
class TablaProductos:
    tiendas: list[str]
    # experto -> clave normalizada -> tiendas que llevan ese producto
    rutas: dict[str, dict[str, set[str]]]
    productos: int
    advertencias: list[str] = field(default_factory=list)


def _marcado(valor: object) -> bool:
    return valor is not None and normalizar(valor) not in _NO_MARCA


def leer_tabla(path: Path, expertos: Iterable[str] = tuple(EXPERTOS)) -> TablaProductos:
    path = Path(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[HOJA_PRODUCTOS] if HOJA_PRODUCTOS in wb.sheetnames else wb[wb.sheetnames[0]]
        filas = ws.iter_rows(values_only=True)
        encabezado = next(filas, None) or ()

        ignorar = {normalizar(c) for c in COLUMNAS_FIJAS + COLUMNAS_INFO}
        por_experto = {normalizar(e): e for e in expertos}
        cols_experto: list[tuple[str, int]] = []
        cols_tienda: list[tuple[str, int]] = []
        for idx, valor in enumerate(encabezado):
            if valor is None or not str(valor).strip():
                continue
            nombre = str(valor).strip()
            clave = normalizar(nombre)
            if clave in ignorar:
                continue
            if clave in por_experto:
                cols_experto.append((por_experto[clave], idx))
            else:
                cols_tienda.append((nombre, idx))

        rutas: dict[str, dict[str, set[str]]] = {e: {} for e, _ in cols_experto}
        origen: dict[tuple[str, str], int] = {}
        advertencias: list[str] = []
        productos = 0
        for n_fila, fila in enumerate(filas, start=2):
            if not fila or all(v is None or not str(v).strip() for v in fila):
                continue
            productos += 1
            tiendas = {t for t, idx in cols_tienda if idx < len(fila) and _marcado(fila[idx])}
            for experto, idx in cols_experto:
                celda = fila[idx] if idx < len(fila) else None
                if celda is None:
                    continue
                for nombre in str(celda).split(SEPARADOR_NOMBRES):
                    clave = normalizar(nombre)
                    if not clave:
                        continue
                    previo = rutas[experto].get(clave)
                    if previo is not None and previo != tiendas:
                        advertencias.append(
                            f"{path.name}: '{nombre.strip()}' ({experto}) esta en las filas "
                            f"{origen[(experto, clave)]} y {n_fila} con distintas tiendas; se usa la union"
                        )
                        previo |= tiendas
                    elif previo is None:
                        rutas[experto][clave] = set(tiendas)
                        origen[(experto, clave)] = n_fila
        return TablaProductos(
            tiendas=[t for t, _ in cols_tienda], rutas=rutas, productos=productos, advertencias=advertencias
        )
    finally:
        wb.close()


@dataclass
class FilaTabla:
    """Una fila de la hoja Productos, tal como esta escrita."""

    fila: int
    linea: str | None
    producto: str | None
    nombres: dict[str, list[str]]  # experto -> nombres (separados por ";")
    tiendas: set[str]


def _columnas_tabla(encabezado: tuple, expertos: Iterable[str]) -> tuple[dict[str, int], list[tuple[str, int]]]:
    """(columna fija/experto -> indice, [(tienda, indice)])."""
    fijas = {normalizar(c): c for c in (*COLUMNAS_FIJAS, *COLUMNAS_INFO)}
    por_experto = {normalizar(e): e for e in expertos}
    cols: dict[str, int] = {}
    tiendas: list[tuple[str, int]] = []
    for idx, valor in enumerate(encabezado):
        if valor is None or not str(valor).strip():
            continue
        clave = normalizar(valor)
        if clave in fijas:
            cols.setdefault(fijas[clave], idx)
        elif clave in por_experto:
            cols.setdefault(por_experto[clave], idx)
        else:
            tiendas.append((str(valor).strip(), idx))
    return cols, tiendas


def leer_filas_tabla(path: Path, expertos: Iterable[str] = tuple(EXPERTOS)) -> tuple[list[str], list[FilaTabla]]:
    """(tiendas, filas) de la hoja Productos, para saber como se llama cada
    producto en cada experto (leer_tabla solo arma las rutas del filtro)."""
    expertos = tuple(expertos)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[HOJA_PRODUCTOS] if HOJA_PRODUCTOS in wb.sheetnames else wb[wb.sheetnames[0]]
        filas = ws.iter_rows(values_only=True)
        cols, cols_tienda = _columnas_tabla(next(filas, None) or (), expertos)
        out: list[FilaTabla] = []
        for n, fila in enumerate(filas, start=2):
            if not fila or all(v is None or not str(v).strip() for v in fila):
                continue

            def celda(nombre: str) -> object:
                i = cols.get(nombre)
                return fila[i] if i is not None and i < len(fila) else None

            nombres = {}
            for e in expertos:
                valor = celda(e)
                if valor is not None:
                    partes = [p.strip() for p in str(valor).split(SEPARADOR_NOMBRES) if p.strip()]
                    if partes:
                        nombres[e] = partes
            out.append(
                FilaTabla(
                    fila=n,
                    linea=None if celda(COL_LINEA) is None else str(celda(COL_LINEA)).strip(),
                    producto=None if celda(COL_PRODUCTO) is None else str(celda(COL_PRODUCTO)).strip(),
                    nombres=nombres,
                    tiendas={t for t, i in cols_tienda if i < len(fila) and _marcado(fila[i])},
                )
            )
        return [t for t, _ in cols_tienda], out
    finally:
        wb.close()


@dataclass
class ProductoAgregado:
    linea: str
    producto: str
    nombres: dict[str, str]  # experto -> nombre
    tiendas: set[str]


def actualizar_tabla(
    origen: Path,
    destino: Path,
    nuevos: list[ProductoAgregado],
    completar: Mapping[int, Mapping[str, str]],
    nota: str,
) -> None:
    """Escribe en `destino` la tabla `origen` con los productos `nuevos`
    agregados al final y, en las filas existentes, los nombres de `completar`
    (fila -> experto -> nombre) en las celdas de experto que estaban vacias. Las
    filas tocadas llevan `nota` en Revisar. Las demas hojas quedan igual."""
    wb = openpyxl.load_workbook(origen)
    try:
        ws = wb[HOJA_PRODUCTOS] if HOJA_PRODUCTOS in wb.sheetnames else wb[wb.sheetnames[0]]
        encabezado = tuple(c.value for c in ws[1])
        cols, cols_tienda = _columnas_tabla(encabezado, EXPERTOS)
        faltan = [c for c in (COL_LINEA, COL_PRODUCTO, *EXPERTOS) if c not in cols]
        if faltan:
            raise ValueError(f"{Path(origen).name}: la hoja Productos no tiene la(s) columna(s) {', '.join(faltan)}")
        col_revisar = cols.get(COL_REVISAR)
        if col_revisar is None:
            col_revisar = len(encabezado)
            ws.cell(row=1, column=col_revisar + 1, value=COL_REVISAR)

        def anotar(fila: int) -> None:
            celda = ws.cell(row=fila, column=col_revisar + 1)
            previo = str(celda.value).strip() if celda.value else ""
            celda.value = f"{previo}; {nota}" if previo else nota

        for fila, nombres in completar.items():
            tocada = False
            for experto, nombre in nombres.items():
                celda = ws.cell(row=fila, column=cols[experto] + 1)
                if celda.value is None or not str(celda.value).strip():
                    celda.value = nombre
                    tocada = True
            if tocada:
                anotar(fila)

        centro = Alignment(horizontal="center")
        # ultima fila con algun valor (max_row cuenta tambien filas vacias con formato)
        ultima = ws.max_row
        while ultima > 1 and all(c.value is None or not str(c.value).strip() for c in ws[ultima]):
            ultima -= 1
        for fila, p in enumerate(nuevos, start=ultima + 1):
            ws.cell(row=fila, column=cols[COL_LINEA] + 1, value=p.linea)
            ws.cell(row=fila, column=cols[COL_PRODUCTO] + 1, value=p.producto)
            for experto, nombre in p.nombres.items():
                ws.cell(row=fila, column=cols[experto] + 1, value=nombre)
            for tienda, idx in cols_tienda:
                if tienda in p.tiendas:
                    celda = ws.cell(row=fila, column=idx + 1, value=MARCA)
                    celda.alignment = centro
            anotar(fila)
        if nuevos and ws.auto_filter.ref:
            ws.auto_filter.ref = ws.dimensions
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        wb.save(destino)
    finally:
        wb.close()


# --------------------------------------------------------------------------- #
# edicion desde la app (vista Homologos)
# --------------------------------------------------------------------------- #
class TablaCambiadaError(Exception):
    """La tabla cambio en disco desde que se leyo para editar (p. ej. se la
    edito en Excel): no se pisa, hay que recargar."""


def version_tabla(path: Path) -> str:
    """Identifica la version en disco de la tabla (para no pisar cambios hechos
    en Excel mientras se editaba en la app)."""
    return str(Path(path).stat().st_mtime_ns)


def leer_para_editar(path: Path) -> dict:
    """La hoja Productos para el editor: {tiendas, version, filas}, cada fila con
    su numero de fila en el archivo (`id`), SUBP, Linea, Producto, el nombre en
    cada experto (texto de la celda, varios nombres separados por ";"), las
    tiendas marcadas y Revisar."""
    path = Path(path)
    version = version_tabla(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[HOJA_PRODUCTOS] if HOJA_PRODUCTOS in wb.sheetnames else wb[wb.sheetnames[0]]
        filas = ws.iter_rows(values_only=True)
        cols, cols_tienda = _columnas_tabla(next(filas, None) or (), EXPERTOS)
        out = []
        for n, fila in enumerate(filas, start=2):
            if not fila or all(v is None or not str(v).strip() for v in fila):
                continue

            def texto(nombre: str) -> str:
                i = cols.get(nombre)
                v = fila[i] if i is not None and i < len(fila) else None
                return "" if v is None else str(v).strip()

            out.append(
                {
                    "id": n,
                    "subp": texto(COL_SUBP),
                    "linea": texto(COL_LINEA),
                    "producto": texto(COL_PRODUCTO),
                    "nombres": {e: texto(e) for e in EXPERTOS},
                    "tiendas": [t for t, i in cols_tienda if i < len(fila) and _marcado(fila[i])],
                    "revisar": texto(COL_REVISAR),
                }
            )
        return {"tiendas": [t for t, _ in cols_tienda], "version": version, "filas": out}
    finally:
        wb.close()


def _validar_edicion(filas: list[dict], tiendas: list[str]) -> list[str]:
    errores: list[str] = []
    donde: dict[tuple[str, str], str] = {}
    for f in filas:
        producto = str(f.get("producto") or "").strip()
        if not producto:
            errores.append("Hay un producto sin nombre (columna Producto)")
            continue
        desconocidas = [t for t in f.get("tiendas") or [] if t not in tiendas]
        if desconocidas:
            errores.append(f"{producto}: tiendas que no estan en la tabla ({', '.join(desconocidas)})")
        for experto in EXPERTOS:
            for nombre in str((f.get("nombres") or {}).get(experto) or "").split(SEPARADOR_NOMBRES):
                clave = normalizar(nombre)
                if not clave:
                    continue
                otro = donde.get((experto, clave))
                if otro is not None and otro != producto:
                    errores.append(f"'{nombre.strip()}' ({experto}) esta en dos productos: {otro} y {producto}")
                donde[(experto, clave)] = producto
    return errores


def guardar_edicion(
    path: Path, filas: list[dict], *, version: str | None, respaldo_dir: Path, nota_nuevas: str | None = None
) -> Path:
    """Reescribe la hoja Productos con `filas` (mismo formato que
    `leer_para_editar`; las que no traen `id` son nuevas) en ese orden. Las
    filas que no vienen se eliminan. Notas y el resto de las hojas se conservan;
    Revisar se conserva salvo en las filas nuevas, que llevan `nota_nuevas`.

    Antes de escribir copia la tabla a `respaldo_dir` y devuelve esa copia.
    Lanza TablaCambiadaError si la tabla cambio en disco desde `version`,
    ValueError si hay filas invalidas (producto sin nombre, un mismo nombre de
    experto en dos productos) y PermissionError si esta abierta en Excel."""
    path = Path(path)
    if version is not None and version != version_tabla(path):
        raise TablaCambiadaError(
            f"{path.name} cambió en disco desde que se abrió (¿se editó en Excel?): recargá la vista"
        )
    wb = openpyxl.load_workbook(path)
    try:
        ws = wb[HOJA_PRODUCTOS] if HOJA_PRODUCTOS in wb.sheetnames else wb[wb.sheetnames[0]]
        encabezado = tuple(c.value for c in ws[1])
        cols, cols_tienda = _columnas_tabla(encabezado, EXPERTOS)
        tiendas = [t for t, _ in cols_tienda]
        errores = _validar_edicion(filas, tiendas)
        if errores:
            raise ValueError("; ".join(dict.fromkeys(errores)))
        for nombre in (COL_LINEA, COL_PRODUCTO, *EXPERTOS):
            if nombre not in cols:
                raise ValueError(f"{path.name}: la hoja Productos no tiene la columna {nombre}")
        col_revisar = cols.get(COL_REVISAR)
        if col_revisar is None:
            col_revisar = len(encabezado)
            ws.cell(row=1, column=col_revisar + 1, value=COL_REVISAR)
        ancho = max(len(encabezado), col_revisar + 1)
        originales = {
            n: [ws.cell(row=n, column=c + 1).value for c in range(ancho)] for n in range(2, ws.max_row + 1)
        }
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)

        centro = Alignment(horizontal="center")
        indices_tienda = {i for _, i in cols_tienda}
        for r, f in enumerate(filas, start=2):
            previa = originales.get(f.get("id")) if f.get("id") else None
            valores = list(previa) if previa else [None] * ancho

            def poner(nombre_col: str, valor: object) -> None:
                i = cols.get(nombre_col)
                if i is not None:
                    valores[i] = valor if valor not in ("", None) else None

            poner(COL_SUBP, str(f.get("subp") or "").strip())
            poner(COL_LINEA, str(f.get("linea") or "").strip())
            poner(COL_PRODUCTO, str(f.get("producto") or "").strip())
            for experto in EXPERTOS:
                poner(experto, str((f.get("nombres") or {}).get(experto) or "").strip())
            marcadas = set(f.get("tiendas") or [])
            for tienda, i in cols_tienda:
                valores[i] = MARCA if tienda in marcadas else None
            if not previa and nota_nuevas:
                valores[col_revisar] = nota_nuevas
            for c, valor in enumerate(valores):
                celda = ws.cell(row=r, column=c + 1, value=valor)
                if c in indices_tienda:
                    celda.alignment = centro
        if ws.auto_filter.ref:
            ws.auto_filter.ref = f"A1:{get_column_letter(ancho)}{max(1, len(filas) + 1)}"

        respaldo_dir = Path(respaldo_dir)
        respaldo_dir.mkdir(parents=True, exist_ok=True)
        respaldo = respaldo_dir / path.name
        n = 2
        while respaldo.exists():
            respaldo = respaldo_dir / f"{path.stem}_{n}{path.suffix}"
            n += 1
        shutil.copy2(path, respaldo)
        # se escribe al lado del respaldo y se reemplaza de una vez (si la tabla
        # esta abierta en Excel, os.replace falla y queda la anterior intacta)
        temporal = respaldo_dir / f".guardando_{path.name}"
        try:
            wb.save(temporal)
            os.replace(temporal, path)
        except PermissionError:
            respaldo.unlink(missing_ok=True)
            raise
        finally:
            if temporal.exists():
                temporal.unlink()
        return respaldo
    finally:
        wb.close()


# --------------------------------------------------------------------------- #
# armado inicial (bootstrap)
# --------------------------------------------------------------------------- #
@dataclass
class _Producto:
    linea: str
    nombre: str
    subp: str | None
    ids: set[str] = field(default_factory=set)
    tiendas: set[str] = field(default_factory=set)
    nombres: dict[str, str] = field(default_factory=dict)  # experto -> nombre(s)
    revisar: list[str] = field(default_factory=list)


@dataclass
class ResumenBootstrap:
    destino: Path
    productos: int
    a_revisar: int
    sin_asignar: dict[str, int]  # experto -> productos del experto que no calzaron


def _sin_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto if not unicodedata.combining(ch)).casefold()


def _tokens(texto: str) -> list[str]:
    texto = _sin_acentos(texto).replace("e.a.", " ea ")
    return [t for t in re.split(r"[^0-9a-z]+", texto) if t]


# Prefijo con el que Experto 1/2 nombran los productos de cada linea
# ("Ltx. Habitacional Ceresita", "E.A. Pajarito Soquina", "Oleo Opaco Sipa").
_PREFIJOS = {"ltx", "ea", "esm", "oleo", "bz", "textura"}
_PREFIJO_LINEA = {
    "latex": "ltx",
    "esm.alagua": "ea",
    "esm.sinteticos": "esm",
    "oleos": "oleo",
    "barnices": "bz",
}


def _puntaje(linea: str, nombre: str, candidato: str) -> tuple[float, bool]:
    """(puntaje 0..~1.2, confiable) de que `candidato` (nombre en el experto) sea
    el homologo `nombre` de la linea `linea`."""
    th = _tokens(nombre)
    tc = _tokens(candidato)
    pref_c = tc[0] if tc and tc[0] in _PREFIJOS else None
    nucleo = tc[1:] if pref_c else tc
    esperado = _PREFIJO_LINEA.get(normalizar(linea))
    if not th or not nucleo:
        return 0.0, False
    sh, sc = set(th), set(nucleo)
    jaccard = len(sh & sc) / len(sh | sc)
    seq = difflib.SequenceMatcher(None, "".join(th), "".join(nucleo)).ratio()
    puntaje = 0.6 * jaccard + 0.4 * seq
    if sh <= sc:  # "Plastikote 13" -> "Revestimiento elastomerico Plastikote 13 (BA)"
        puntaje += 0.2
    prefijo_ok = esperado is None or pref_c is None or pref_c == esperado
    if esperado is not None and pref_c is not None:
        puntaje += 0.2 if pref_c == esperado else -0.3
    confiable = prefijo_ok and (sh <= sc or "".join(th) == "".join(nucleo)) and seq >= 0.8
    return puntaje, confiable


def _asignar(
    productos: list[_Producto],
    catalogo: Iterable[str],
    *,
    texto: Callable[[str], str] = lambda c: c,
    admite: Callable[[_Producto, str], bool] = lambda p, c: True,
) -> tuple[dict[int, tuple[str, bool]], set[str]]:
    """Asignacion greedy 1 a 1 homologo -> nombre del experto por puntaje.
    `texto` da la parte del nombre del experto a comparar y `admite` descarta
    pares imposibles."""
    candidatos = list(catalogo)
    pares = []
    for i, p in enumerate(productos):
        for c in candidatos:
            if not admite(p, c):
                continue
            puntaje, confiable = _puntaje(p.linea, p.nombre, texto(c))
            if puntaje >= 0.45:
                pares.append((puntaje, i, c, confiable))
    pares.sort(key=lambda x: -x[0])
    asignados: dict[int, tuple[str, bool]] = {}
    usados: set[str] = set()
    for _, i, c, confiable in pares:
        if i in asignados or c in usados:
            continue
        asignados[i] = (c, confiable)
        usados.add(c)
    return asignados, set(candidatos) - usados


def _ids_a_clave_e3(xdata_path: Path) -> dict[str, str]:
    """ID_TINT -> "group_code / product_code" desde el xData_DATACOMPLETA."""
    wb = openpyxl.load_workbook(xdata_path, read_only=True, data_only=True)
    try:
        nombre = next((n for n in wb.sheetnames if n.strip().lower() == "formulas"), wb.sheetnames[0])
        filas = wb[nombre].iter_rows(values_only=True)
        encabezado = [normalizar(h) for h in next(filas)]
        i_id = next(i for i, h in enumerate(encabezado) if h in ("id_tint", "id", "tint_id"))
        i_g, i_p = encabezado.index("group_code"), encabezado.index("product_code")
        out = {}
        for fila in filas:
            if i_id >= len(fila) or fila[i_id] is None:
                continue
            out[str(fila[i_id]).strip()] = f"{str(fila[i_g] or '').strip()}{KEY_SEP}{str(fila[i_p] or '').strip()}"
        return out
    finally:
        wb.close()


def _leer_homologos(homologos_path: Path, tiendas: list[str], log) -> list[_Producto]:
    productos: dict[tuple[str, str], _Producto] = {}
    for tienda in tiendas:
        log(f"Leyendo hoja '{tienda}' de {homologos_path.name}…")
        hoja = homologos_editor.parse_sheet(homologos_path, tienda)
        for linea in hoja.lineas:
            for h in linea.homologos:
                p = productos.setdefault(
                    (linea.nombre, h.nombre), _Producto(linea=linea.nombre, nombre=h.nombre, subp=h.path)
                )
                if h.ids:
                    p.ids.update(h.ids)
                    p.tiendas.add(tienda)
    return list(productos.values())


def bootstrap_tabla(
    homologos_path: Path,
    xdata_path: Path | None,
    expertos: Mapping[str, Path | None],
    destino: Path,
    *,
    tiendas: list[str] | None = None,
    on_log: Callable[[str], None] | None = None,
) -> ResumenBootstrap:
    """Genera homologos_TINT.xlsx en `destino` (no sobreescribe: si existe,
    lanza FileExistsError). `expertos` mapea label -> archivo experto (.xlsx /
    .xlsm) o None si no esta disponible."""
    log = on_log or (lambda _msg: None)
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe; no se sobreescribe")

    hojas = homologos_editor.list_sheet_names(homologos_path)
    tiendas = [t for t in hojas if tiendas is None or t in tiendas]
    productos = _leer_homologos(Path(homologos_path), tiendas, log)

    catalogos: dict[str, Counter] = {}
    for label, path in expertos.items():
        if path is None:
            continue
        log(f"Leyendo productos de {Path(path).name}…")
        catalogos[label] = contar_claves(Path(path), EXPERTOS[label].key_headers)

    # Experto 3: nombre exacto via ID_TINT -> xData (mismo formato que Experto 3)
    ids_e3 = {}
    if xdata_path is not None:
        log(f"Leyendo ID_TINT de {Path(xdata_path).name}…")
        ids_e3 = _ids_a_clave_e3(Path(xdata_path))

    sin_asignar: dict[str, list[tuple[str, int]]] = {}
    for label in EXPERTOS:
        catalogo = catalogos.get(label)
        if label == "Experto 3" and ids_e3:
            usados = set()
            en_catalogo = {normalizar(k) for k in catalogo} if catalogo is not None else set()
            for p in productos:
                claves = Counter(ids_e3[i] for i in p.ids if i in ids_e3)
                if not claves:
                    if p.ids:
                        p.revisar.append(f"{label}: sus ID_TINT no estan en el xData")
                    continue
                p.nombres[label] = SEPARADOR_NOMBRES.join(c for c, _ in claves.most_common())
                usados.update(normalizar(c) for c in claves)
                if len(claves) > 1:
                    p.revisar.append(f"{label}: el homologo mezcla varios productos")
                if catalogo is not None and not any(normalizar(c) in en_catalogo for c in claves):
                    p.revisar.append(f"{label}: no esta en el experto actual")
            # homologos sin ID_TINT (pendientes): se sugiere por nombre dentro de su linea
            pendientes = [p for p in productos if label not in p.nombres]
            resto = [c for c in (catalogo or {}) if normalizar(c) not in usados]
            if pendientes and resto:
                asignados, _ = _asignar(
                    pendientes,
                    resto,
                    texto=lambda c: c.split(KEY_SEP, 1)[-1],
                    admite=lambda p, c: normalizar(c.split(KEY_SEP, 1)[0]) == normalizar(p.linea),
                )
                for i, p in enumerate(pendientes):
                    if i in asignados:
                        p.nombres[label] = asignados[i][0]
                        usados.add(normalizar(asignados[i][0]))
                        p.revisar.append(f"{label}: nombre sugerido")
            if catalogo is not None:
                sin_asignar[label] = sorted((c, n) for c, n in catalogo.items() if normalizar(c) not in usados)
            continue
        if catalogo is None:
            continue
        asignados, libres = _asignar(productos, catalogo)
        for i, p in enumerate(productos):
            if i in asignados:
                nombre, confiable = asignados[i]
                p.nombres[label] = nombre
                if not confiable:
                    p.revisar.append(f"{label}: nombre sugerido")
            elif p.ids:
                p.revisar.append(f"{label}: sin coincidencia")
        sin_asignar[label] = sorted((c, catalogo[c]) for c in libres)

    # Si falta un experto (p.ej. Experto 1 todavia en .xls), se copia el nombre
    # de otro experto con la misma columna clave: los nombres de Experto 1 y 2
    # coinciden salvo espacios, que la comparacion ignora.
    for label, path in expertos.items():
        if path is not None or label in catalogos:
            continue
        fuente = next(
            (
                otro
                for otro in catalogos
                if EXPERTOS[otro].key_headers == EXPERTOS[label].key_headers and otro != label
            ),
            None,
        )
        for p in productos:
            if fuente and fuente in p.nombres:
                p.nombres[label] = p.nombres[fuente]
                p.revisar.append(f"{label}: copiado de {fuente} (no habia archivo)")
            elif p.ids:
                p.revisar.append(f"{label}: sin nombre (no habia archivo)")

    for p in productos:
        if not p.ids:
            p.revisar.append("sin formulas en los homologos")

    _escribir_tabla(destino, productos, tiendas, sin_asignar)
    return ResumenBootstrap(
        destino=destino,
        productos=len(productos),
        a_revisar=sum(1 for p in productos if p.revisar),
        sin_asignar={k: len(v) for k, v in sin_asignar.items()},
    )


def _escribir_tabla(
    destino: Path,
    productos: list[_Producto],
    tiendas: list[str],
    sin_asignar: Mapping[str, list[tuple[str, int]]],
) -> None:
    bold = Font(bold=True)
    fondo = PatternFill("solid", fgColor="DDEBF7")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = HOJA_PRODUCTOS
    expertos = list(EXPERTOS)
    ws.append([*COLUMNAS_FIJAS, *expertos, *tiendas, COL_REVISAR])
    for p in productos:
        ws.append(
            [
                p.subp,
                p.linea,
                p.nombre,
                *(p.nombres.get(e) for e in expertos),
                *(MARCA if t in p.tiendas else None for t in tiendas),
                "; ".join(p.revisar) or None,
            ]
        )
    for cell in ws[1]:
        cell.font = bold
        cell.fill = fondo
    anchos = [11, 16, 34, *([36] * len(expertos)), *([11] * len(tiendas)), 60]
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    for fila in ws.iter_rows(min_row=2, min_col=len(COLUMNAS_FIJAS) + len(expertos) + 1,
                             max_col=len(COLUMNAS_FIJAS) + len(expertos) + len(tiendas)):
        for cell in fila:
            cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions

    ws2 = wb.create_sheet(HOJA_SIN_ASIGNAR)
    ws2.append(["Experto", "Producto en el experto", "Filas"])
    for label, items in sin_asignar.items():
        for nombre, filas in items:
            ws2.append([label, nombre, filas])
    for cell in ws2[1]:
        cell.font = bold
        cell.fill = fondo
    ws2.column_dimensions["A"].width = 12
    ws2.column_dimensions["B"].width = 50
    ws2.column_dimensions["C"].width = 10
    ws2.freeze_panes = "A2"

    ws3 = wb.create_sheet(HOJA_LEEME)
    for linea in (
        "Tabla de productos de TINT_SIS: que tiendas lleva cada producto y como se llama en cada experto.",
        "",
        "- Una fila por producto. Columnas Experto 1/2/3: nombre del producto en ese experto",
        "  (Experto 1 y 2: columna 'Producto'; Experto 3: 'group_code / product_code').",
        "  Varios nombres en una celda se separan con ';'. Se comparan sin acentos, mayusculas ni espacios.",
        "- Columnas de tienda: una 'x' = la tienda lleva ese producto. Sin marcas = no va a ninguna tienda.",
        "- 'Revisar' es solo informativa: indica nombres sugeridos o faltantes a confirmar.",
        "- Hoja 'Sin asignar': productos que traen los expertos y no calzaron con ninguna fila.",
        "  Si un experto trae un producto que no esta en esta tabla, el ciclo lo avisa y no lo entrega.",
    ):
        ws3.append([linea])
    ws3.column_dimensions["A"].width = 110

    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
