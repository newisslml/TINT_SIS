"""Filtra por tienda las filas de la hoja de formulas de un .xlsx/.xlsm,
conservando el resto del libro tal cual.

Los softwares importan el libro del experto entero: Tintwise Lab (Experto 2,
.xlsm) trae ademas las hojas Colorants/Bases/Cans/Settings, macros y controles
ActiveX; Corob/Santint (Experto 3) traen la hoja IntegrityData. Cargar esos
libros con openpyxl no es viable (~186k filas x hasta 137 columnas en memoria,
y ademas pierde macros/controles), asi que se trabaja directo sobre el paquete
zip:

  - todas las partes del libro se copian byte a byte, salvo el XML de la hoja
    de formulas (y workbook.xml, para ajustar el rango del autofiltro);
  - la hoja se recorre fila por fila en streaming: la fila 1 (encabezado) se
    copia tal cual -en Experto 2 lleva formulas que apuntan a Settings, y el
    calcChain solo referencia esa fila, asi que queda valido- y cada fila de
    datos se manda a las tiendas que llevan su producto, renumerada para que
    las filas queden contiguas;
  - se actualizan <dimension>, <autoFilter ref> y el nombre definido
    _xlnm._FilterDatabase al nuevo ultimo numero de fila.

Una sola lectura del experto genera los archivos de todas sus tiendas.
El archivo de origen no se modifica.
"""
from __future__ import annotations

import html
import os
import posixpath
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.expertos import clave_visible, normalizar

ProgressCallback = Callable[[dict], None]

HOJA_FORMULAS = "Formulas"

_CHUNK = 1 << 20

_SHEETDATA_RE = re.compile(rb"<((?:[A-Za-z_][\w.-]*:)?)sheetData\b[^>]*?(/?)>")
_CELL_RE = re.compile(rb"<(?:[\w.-]+:)?c\b([^>]*?)(?:/>|>(.*?)</(?:[\w.-]+:)?c>)", re.S)
_ATTR_R_RE = re.compile(rb'\br="([A-Z]+)(\d+)"')
_ATTR_T_RE = re.compile(rb'\bt="(\w+)"')
_ROW_R_RE = re.compile(rb'\br="(\d+)"')
_V_RE = re.compile(rb"<((?:[\w.-]+:)?)v>(.*?)</(?:[\w.-]+:)?v>", re.S)
_T_RE = re.compile(rb"<(?:[\w.-]+:)?t(?:\s[^>]*)?>(.*?)</(?:[\w.-]+:)?t>", re.S)
_F_RE = re.compile(rb"<(?:[\w.-]+:)?f\b[^>]*?(?:/>|>.*?</(?:[\w.-]+:)?f>)", re.S)
# r="<numero>" de la fila y r="<COL><numero>" de cada celda (solo dentro de esas
# etiquetas, nunca en el texto de una celda); se reemplaza el numero por un
# marcador (\x00, invalido en XML) y despues por el numero nuevo de cada tienda.
_R_NUM_RE = re.compile(rb'(<(?:[\w.-]+:)?(?:row|c)\b[^>]*?\br="[A-Z]*)\d+(")')
_DIM_RE = re.compile(rb'(<(?:[\w.-]+:)?dimension\b[^>]*?\bref="[A-Z]+\d+:[A-Z]+)(\d+)(")')
_AUTOFILTER_RE = re.compile(rb'(<(?:[\w.-]+:)?autoFilter\b[^>]*?\bref="[A-Z]+\d+:[A-Z]+)(\d+)(")')
_DEFINED_NAME_RE = re.compile(rb"(<definedName\b([^>]*)>)([^<]*)(</definedName>)")


class FormatoExpertoError(ValueError):
    """El archivo no tiene la estructura esperada (hoja, encabezados, xml)."""


@dataclass
class ResultadoFiltro:
    hoja: str
    filas_leidas: int = 0
    filas_por_tienda: dict[str, int] = field(default_factory=dict)
    # clave visible del producto -> filas que no se entregaron a ninguna tienda
    # porque el producto no esta en la tabla de productos
    sin_asignar: Counter = field(default_factory=Counter)
    filas_sin_clave: int = 0


# --------------------------------------------------------------------------- #
# estructura del paquete
# --------------------------------------------------------------------------- #
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _rels_path(part: str) -> str:
    carpeta, nombre = posixpath.split(part)
    return posixpath.join(carpeta, "_rels", nombre + ".rels")


def _resolver(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def _relaciones(z: zipfile.ZipFile, part: str) -> list[tuple[str, str, str]]:
    """(Id, Type, parte destino) de las relaciones de `part`."""
    try:
        root = ET.fromstring(z.read(_rels_path(part)))
    except KeyError:
        return []
    out = []
    for rel in root:
        if rel.get("TargetMode") == "External":
            continue
        out.append((rel.get("Id"), rel.get("Type") or "", _resolver(part, rel.get("Target") or "")))
    return out


@dataclass
class _Libro:
    workbook_part: str
    hojas: list[tuple[str, str]]  # (nombre, parte) en el orden del libro
    shared_strings_part: str | None


def _estructura(z: zipfile.ZipFile) -> _Libro:
    wb_part = next(
        (destino for _, tipo, destino in _relaciones(z, "") if tipo.endswith("/officeDocument")),
        "xl/workbook.xml",
    )
    rels = {rid: (tipo, destino) for rid, tipo, destino in _relaciones(z, wb_part)}
    root = ET.fromstring(z.read(wb_part))
    hojas = []
    for el in root.iter():
        if _local(el.tag) != "sheet":
            continue
        rid = next((v for k, v in el.attrib.items() if _local(k) == "id"), None)
        if rid in rels:
            hojas.append((el.get("name") or "", rels[rid][1]))
    sst = next((destino for tipo, destino in rels.values() if tipo.endswith("/sharedStrings")), None)
    if not hojas:
        raise FormatoExpertoError("el libro no tiene hojas")
    return _Libro(workbook_part=wb_part, hojas=hojas, shared_strings_part=sst)


def _elegir_hoja(libro: _Libro, nombre: str) -> tuple[int, str, str]:
    for idx, (n, part) in enumerate(libro.hojas):
        if n.strip().lower() == nombre.strip().lower():
            return idx, n, part
    n, part = libro.hojas[0]
    return 0, n, part


def _leer_shared_strings(z: zipfile.ZipFile, part: str | None) -> list[str]:
    if part is None:
        return []
    out: list[str] = []
    with z.open(part) as f:
        for _, el in ET.iterparse(f, events=("end",)):
            if _local(el.tag) != "si":
                continue
            partes = []
            for hijo in el:
                nombre = _local(hijo.tag)
                if nombre == "t":
                    partes.append(hijo.text or "")
                elif nombre == "r":  # texto enriquecido; rPh (fonetica) se ignora
                    partes.extend(t.text or "" for t in hijo if _local(t.tag) == "t")
            out.append("".join(partes))
            el.clear()
    return out


# --------------------------------------------------------------------------- #
# lectura de la hoja en streaming
# --------------------------------------------------------------------------- #
class _LectorHoja:
    """Parte el XML de una hoja en prefijo (hasta <sheetData>), filas y sufijo
    (desde </sheetData>) sin cargarlo entero en memoria."""

    def __init__(self, f):
        self._f = f
        self.prefijo = b""
        self.sufijo = b""
        self._buf = b""
        self._pfx = b""
        self._vacia = False

    def _leer_mas(self) -> bool:
        chunk = self._f.read(_CHUNK)
        if not chunk:
            return False
        self._buf += chunk
        return True

    def abrir(self) -> None:
        while True:
            m = _SHEETDATA_RE.search(self._buf)
            if m:
                break
            if not self._leer_mas():
                raise FormatoExpertoError("la hoja no tiene <sheetData>")
        self._pfx = m.group(1)
        self.prefijo = self._buf[: m.end()]
        self._buf = self._buf[m.end() :]
        self._vacia = m.group(2) == b"/"

    def filas(self) -> Iterator[bytes]:
        if self._vacia:
            self.sufijo = self._buf + self._f.read()
            return
        row_open = b"<" + self._pfx + b"row"
        row_close = b"</" + self._pfx + b"row>"
        fin = b"</" + self._pfx + b"sheetData>"
        buf = self._buf
        pos = 0
        while True:
            i = buf.find(b"<", pos)
            if i == -1 or len(buf) - i < len(fin) + 1:
                chunk = self._f.read(_CHUNK)
                if not chunk:
                    raise FormatoExpertoError("la hoja termina sin </sheetData>")
                buf = buf[pos:] + chunk
                pos = 0
                continue
            if buf.startswith(fin, i):
                self.sufijo = buf[i:] + self._f.read()
                return
            if not (buf.startswith(row_open, i) and buf[i + len(row_open) : i + len(row_open) + 1] in (b" ", b">", b"/")):
                raise FormatoExpertoError("contenido inesperado dentro de <sheetData>")
            j = buf.find(b">", i)
            if j == -1:
                chunk = self._f.read(_CHUNK)
                if not chunk:
                    raise FormatoExpertoError("fila truncada")
                buf = buf[pos:] + chunk
                pos = 0
                continue
            if buf[j - 1 : j] == b"/":
                yield buf[i : j + 1]
                pos = j + 1
                continue
            k = buf.find(row_close, j)
            if k == -1:
                chunk = self._f.read(_CHUNK)
                if not chunk:
                    raise FormatoExpertoError("fila truncada")
                buf = buf[pos:] + chunk
                pos = 0
                continue
            fin_fila = k + len(row_close)
            yield buf[i:fin_fila]
            pos = fin_fila


def _col_letras(idx: int) -> bytes:
    letras = ""
    idx += 1
    while idx:
        idx, resto = divmod(idx - 1, 26)
        letras = chr(65 + resto) + letras
    return letras.encode()


def _col_indice(letras: bytes) -> int:
    n = 0
    for ch in letras:
        n = n * 26 + (ch - 64)
    return n - 1


def _celdas(fila: bytes) -> Iterator[tuple[bytes, bytes, bytes | None]]:
    """(columna, atributos, contenido) de cada celda de la fila."""
    siguiente = 0
    for m in _CELL_RE.finditer(fila):
        attrs = m.group(1)
        r = _ATTR_R_RE.search(attrs)
        if r:
            col = r.group(1)
            siguiente = _col_indice(col) + 1
        else:
            col = _col_letras(siguiente)
            siguiente += 1
        yield col, attrs, m.group(2)


def _valor(attrs: bytes, contenido: bytes | None, sst: list[str]) -> str | None:
    if contenido is None:
        return None
    t = _ATTR_T_RE.search(attrs)
    tipo = t.group(1) if t else b"n"
    if tipo == b"inlineStr":
        return html.unescape("".join(x.decode("utf-8") for x in _T_RE.findall(contenido)))
    v = _V_RE.search(contenido)
    if not v:
        return None
    crudo = v.group(2).decode("utf-8")
    if tipo == b"s":
        try:
            return sst[int(crudo)]
        except (ValueError, IndexError):
            return None
    return html.unescape(crudo)


def _encabezados(fila: bytes, sst: list[str]) -> dict[str, bytes]:
    """encabezado normalizado -> letra de columna (primera aparicion)."""
    out: dict[str, bytes] = {}
    for col, attrs, contenido in _celdas(fila):
        valor = _valor(attrs, contenido, sst)
        if valor is None:
            continue
        out.setdefault(normalizar(valor), col)
    return out


def _valores_clave(fila: bytes, cols: dict[bytes, int], sst: list[str]) -> list[str | None]:
    valores: list[str | None] = [None] * len(cols)
    encontrados = 0
    for col, attrs, contenido in _celdas(fila):
        pos = cols.get(col)
        if pos is None:
            continue
        valores[pos] = _valor(attrs, contenido, sst)
        encontrados += 1
        if encontrados == len(cols):
            break
    return valores


def _quitar_formulas(fila: bytes) -> bytes:
    """Deja solo el valor calculado de las celdas con formula (las formulas de
    filas de datos no sobreviven a la renumeracion). Las de texto pasan a
    inlineStr, que es el tipo valido para un texto sin formula."""

    def celda(m: re.Match) -> bytes:
        completa = m.group(0)
        if not _F_RE.search(completa):
            return completa
        completa = _F_RE.sub(b"", completa)
        if b't="str"' in completa:
            completa = completa.replace(b't="str"', b't="inlineStr"', 1)
            completa = _V_RE.sub(
                lambda v: b"<" + v.group(1) + b"is><" + v.group(1) + b"t>" + v.group(2)
                + b"</" + v.group(1) + b"t></" + v.group(1) + b"is>",
                completa,
                count=1,
            )
        return completa

    return _CELL_RE.sub(celda, fila)


# --------------------------------------------------------------------------- #
# escritura
# --------------------------------------------------------------------------- #
def _ajustar_workbook(xml: bytes, sheet_idx: int, ultima_fila: int) -> bytes:
    def dn(m: re.Match) -> bytes:
        attrs = m.group(2)
        if b'name="_xlnm._FilterDatabase"' not in attrs:
            return m.group(0)
        local = re.search(rb'localSheetId="(\d+)"', attrs)
        if not local or int(local.group(1)) != sheet_idx:
            return m.group(0)
        valor = re.sub(rb"(:\$?[A-Z]+\$?)(\d+)$", rb"\g<1>" + str(ultima_fila).encode(), m.group(3))
        return m.group(1) + valor + m.group(4)

    return _DEFINED_NAME_RE.sub(dn, xml)


def _sin_calc_chain(z: zipfile.ZipFile, libro: _Libro) -> dict[str, bytes | None]:
    """Partes a reemplazar (bytes) u omitir (None) para quitar calcChain.xml."""
    cambios: dict[str, bytes | None] = {}
    rels_part = _rels_path(libro.workbook_part)
    calc = next(
        (d for _, t, d in _relaciones(z, libro.workbook_part) if t.endswith("/calcChain")),
        None,
    )
    if calc is None:
        return cambios
    cambios[calc] = None
    rels_xml = z.read(rels_part)
    cambios[rels_part] = re.sub(rb"<Relationship\b[^>]*?/calcChain\"[^>]*/>", b"", rels_xml)
    ct_xml = z.read("[Content_Types].xml")
    cambios["[Content_Types].xml"] = re.sub(
        rb'<Override\b[^>]*PartName="/' + re.escape(calc.encode()) + rb'"[^>]*/>', b"", ct_xml
    )
    return cambios


def _info_nueva(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    # writestr/open("w") completan offset y tamaños sobre el ZipInfo que reciben:
    # nunca pasarles el del libro de origen (se sigue leyendo para las demas
    # tiendas y quedaria apuntando al archivo de salida).
    zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    zi.compress_type = info.compress_type
    zi.external_attr = info.external_attr
    zi.create_system = info.create_system
    return zi


def _escribir_libro(
    z: zipfile.ZipFile,
    destino: Path,
    hoja_part: str,
    cabeza: bytes,
    filas_tmp: Path,
    sufijo: bytes,
    reemplazos: Mapping[str, bytes | None],
) -> None:
    parcial = destino.with_name(destino.name + ".part")
    try:
        with zipfile.ZipFile(parcial, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in z.infolist():
                nombre = info.filename
                if nombre == hoja_part:
                    zi = _info_nueva(info)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    with zout.open(zi, "w") as w:
                        w.write(cabeza)
                        with open(filas_tmp, "rb") as r:
                            shutil.copyfileobj(r, w, _CHUNK)
                        w.write(sufijo)
                elif nombre in reemplazos:
                    data = reemplazos[nombre]
                    if data is not None:
                        zout.writestr(_info_nueva(info), data)
                else:
                    zout.writestr(_info_nueva(info), z.read(nombre))
        os.replace(parcial, destino)
    finally:
        if parcial.exists():
            parcial.unlink()


# --------------------------------------------------------------------------- #
# API publica
# --------------------------------------------------------------------------- #
def filtrar_libro(
    src: Path,
    destinos: Mapping[str, Path],
    rutas: Mapping[str, set[str]],
    key_headers: Sequence[str],
    *,
    hoja: str = HOJA_FORMULAS,
    on_progress: ProgressCallback | None = None,
    progress_every: int = 2000,
) -> ResultadoFiltro:
    """Genera, por cada tienda de `destinos`, una copia del libro `src` cuya hoja
    de formulas (`hoja`, o la primera si no existe) contiene solo el encabezado y
    las filas de los productos que esa tienda lleva.

    `rutas` mapea clave de producto normalizada (ver expertos.clave_normalizada)
    -> tiendas que lo llevan (un set vacio = producto conocido que no va a
    ninguna tienda). Las filas cuyo producto no esta en `rutas` no se entregan y
    se cuentan en `ResultadoFiltro.sin_asignar`.

    `on_progress` recibe {leidas, total} cada `progress_every` filas y
    {guardando: True} antes de armar los archivos de salida."""
    src = Path(src)
    tmp_dir = Path(tempfile.mkdtemp(prefix="tint_filtro_"))
    tmps: dict[str, Path] = {}
    handles: dict[str, object] = {}
    try:
        with zipfile.ZipFile(src) as z:
            libro = _estructura(z)
            sheet_idx, sheet_name, sheet_part = _elegir_hoja(libro, hoja)
            sst = _leer_shared_strings(z, libro.shared_strings_part)
            resultado = ResultadoFiltro(hoja=sheet_name, filas_por_tienda={t: 0 for t in destinos})

            for i, tienda in enumerate(destinos):
                tmps[tienda] = tmp_dir / f"{i}.rows"
                handles[tienda] = open(tmps[tienda], "wb", buffering=_CHUNK)

            with z.open(sheet_part) as f:
                lector = _LectorHoja(f)
                lector.abrir()
                dim = _DIM_RE.search(lector.prefijo)
                filas_iter = lector.filas()

                encabezado = next(filas_iter, None)
                if encabezado is None:
                    raise FormatoExpertoError(f"la hoja '{sheet_name}' de {src.name} no tiene encabezado")
                r_enc = _ROW_R_RE.search(encabezado[: encabezado.find(b">") + 1])
                fila_enc = int(r_enc.group(1)) if r_enc else 1
                total = int(dim.group(2)) - fila_enc if dim else None

                columnas = _encabezados(encabezado, sst)
                faltan = [h for h in key_headers if h not in columnas]
                if faltan:
                    raise FormatoExpertoError(
                        f"{src.name}: la hoja '{sheet_name}' no tiene la(s) columna(s) "
                        f"{', '.join(faltan)} (se buscan por encabezado)"
                    )
                cols_clave = {columnas[h]: i for i, h in enumerate(key_headers)}

                siguiente = {t: fila_enc + 1 for t in destinos}
                hubo_formulas = False
                for fila in filas_iter:
                    resultado.filas_leidas += 1
                    valores = _valores_clave(fila, cols_clave, sst)
                    if all(v is None or not str(v).strip() for v in valores):
                        resultado.filas_sin_clave += 1
                    else:
                        visible = clave_visible(valores)
                        tiendas = rutas.get(normalizar(visible))
                        if tiendas is None:
                            resultado.sin_asignar[visible] += 1
                        else:
                            destino_filas = [t for t in destinos if t in tiendas]
                            if destino_filas:
                                if (b"<f" in fila or b":f" in fila) and _F_RE.search(fila):
                                    fila = _quitar_formulas(fila)
                                    hubo_formulas = True
                                plantilla = _R_NUM_RE.sub(b"\\1\x00\\2", fila)
                                for t in destino_filas:
                                    handles[t].write(plantilla.replace(b"\x00", str(siguiente[t]).encode()))
                                    siguiente[t] += 1
                    if on_progress is not None and resultado.filas_leidas % progress_every == 0:
                        on_progress({"leidas": resultado.filas_leidas, "total": total})

                prefijo, sufijo = lector.prefijo, lector.sufijo

            if on_progress is not None:
                on_progress({"leidas": resultado.filas_leidas, "total": resultado.filas_leidas})
                on_progress({"guardando": True})

            for h in handles.values():
                h.close()

            base_reemplazos = _sin_calc_chain(z, libro) if hubo_formulas else {}
            wb_xml = z.read(libro.workbook_part)
            for tienda, destino in destinos.items():
                destino = Path(destino)
                destino.parent.mkdir(parents=True, exist_ok=True)
                ultima = siguiente[tienda] - 1
                resultado.filas_por_tienda[tienda] = ultima - fila_enc
                num = str(ultima).encode()
                cabeza = _DIM_RE.sub(rb"\g<1>" + num + rb"\g<3>", prefijo, count=1) + encabezado
                suf = _AUTOFILTER_RE.sub(rb"\g<1>" + num + rb"\g<3>", sufijo, count=1)
                reemplazos = dict(base_reemplazos)
                reemplazos[libro.workbook_part] = _ajustar_workbook(wb_xml, sheet_idx, ultima)
                _escribir_libro(z, destino, sheet_part, cabeza, tmps[tienda], suf, reemplazos)
        return resultado
    finally:
        for h in handles.values():
            if not h.closed:
                h.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def contar_claves(src: Path, key_headers: Sequence[str], *, hoja: str = HOJA_FORMULAS) -> Counter:
    """Clave visible de producto -> cantidad de filas, recorriendo la hoja de
    formulas con el mismo lector que `filtrar_libro` (se usa para armar y
    revisar la tabla de productos)."""
    conteo: Counter = Counter()
    with zipfile.ZipFile(src) as z:
        libro = _estructura(z)
        _, sheet_name, sheet_part = _elegir_hoja(libro, hoja)
        sst = _leer_shared_strings(z, libro.shared_strings_part)
        with z.open(sheet_part) as f:
            lector = _LectorHoja(f)
            lector.abrir()
            filas_iter = lector.filas()
            encabezado = next(filas_iter, None)
            if encabezado is None:
                raise FormatoExpertoError(f"la hoja '{sheet_name}' de {Path(src).name} no tiene encabezado")
            columnas = _encabezados(encabezado, sst)
            faltan = [h for h in key_headers if h not in columnas]
            if faltan:
                raise FormatoExpertoError(
                    f"{Path(src).name}: la hoja '{sheet_name}' no tiene la(s) columna(s) {', '.join(faltan)}"
                )
            cols_clave = {columnas[h]: i for i, h in enumerate(key_headers)}
            for fila in filas_iter:
                valores = _valores_clave(fila, cols_clave, sst)
                if all(v is None or not str(v).strip() for v in valores):
                    continue
                conteo[clave_visible(valores)] += 1
    return conteo
