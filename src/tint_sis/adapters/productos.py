"""Tabla de productos (productos_TINT.xlsx): que tiendas lleva cada producto y
como se llama ese producto en cada archivo experto.

Reemplaza al cruce por ID_TINT: en homologos_TINT.xlsx cada tienda toma
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

`bootstrap_tabla` arma la primera version a partir de homologos_TINT.xlsx
(tiendas por producto), el xData_DATACOMPLETA con ID_TINT (nombre exacto en
Experto 3) y los catalogos de los expertos (nombres sugeridos en Experto 1/2,
marcados para revisar).
"""
from __future__ import annotations

import difflib
import re
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
    """Genera productos_TINT.xlsx en `destino` (no sobreescribe: si existe,
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
