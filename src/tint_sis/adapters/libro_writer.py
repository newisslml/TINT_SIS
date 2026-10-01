"""Reescribe la hoja de formulas de un libro plantilla con filas nuevas,
conservando el resto del libro byte a byte (macros, ActiveX, hojas auxiliares).

Lo usa la preparacion del experto (preparar.py) para generar Experto 2 (.xlsm de
Tintwise) y Experto 3 (Santint/Corob) a partir del archivo maestro: el libro del
ciclo anterior hace de plantilla y solo se reemplazan las filas de datos de su
hoja de formulas. Igual que sheet_filter, se trabaja sobre el paquete zip:

  - el encabezado (fila 1) se copia tal cual: en Experto 2 lleva formulas que
    el calcChain referencia, asi que el calcChain sigue siendo valido;
  - cada celda nueva toma el estilo (s="..") que tenia esa columna en la
    primera fila de datos de la plantilla, asi no cambia el formato numerico;
  - los textos van a sharedStrings como en los originales: se reutiliza el
    indice de un texto que ya existe y los nuevos se agregan al final (las otras
    hojas siguen apuntando a los mismos indices). Si la plantilla no tiene
    sharedStrings, van como texto en la celda (inlineStr);
  - se ajustan <dimension>, <autoFilter> y _xlnm._FilterDatabase.

La plantilla no se modifica.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from tint_sis.adapters.sheet_filter import (
    _AUTOFILTER_RE,
    _ATTR_R_RE,
    _CELL_RE,
    _CHUNK,
    _DIM_RE,
    _ROW_R_RE,
    HOJA_FORMULAS,
    FormatoExpertoError,
    Valor,
    _ajustar_workbook,
    _celdas,
    _col_indice,
    _col_letras,
    _elegir_hoja,
    _escribir_libro,
    _estructura,
    _leer_shared_strings,
    _LectorHoja,
    _numero,
    _sst_con_nuevos,
    _t,
    _valor,
)

ProgressCallback = Callable[[dict], None]

_ATTR_S_RE = re.compile(rb'\bs="(\d+)"')


@dataclass
class ResultadoEscritura:
    hoja: str
    filas: int
    textos_nuevos: int


def encabezado(libro: Path, hoja: str = HOJA_FORMULAS) -> list[str | None]:
    """Valores de la fila de encabezado de la hoja de formulas (el resultado
    guardado, tambien en las celdas con formula), por posicion de columna."""
    with zipfile.ZipFile(libro) as z:
        est = _estructura(z)
        _, nombre, part = _elegir_hoja(est, hoja)
        sst = _leer_shared_strings(z, est.shared_strings_part)
        with z.open(part) as f:
            lector = _LectorHoja(f)
            lector.abrir()
            fila = next(lector.filas(), None)
    if fila is None:
        raise FormatoExpertoError(f"la hoja '{nombre}' de {Path(libro).name} no tiene encabezado")
    valores: dict[int, str | None] = {}
    for col, attrs, contenido in _celdas(fila):
        valores[_col_indice(col)] = _valor(attrs, contenido, sst)
    n = max(valores) + 1 if valores else 0
    return [valores.get(i) for i in range(n)]


def reescribir_hoja(
    plantilla: Path,
    destino: Path,
    filas: Iterable[Sequence[Valor]],
    *,
    hoja: str = HOJA_FORMULAS,
    total: int | None = None,
    on_progress: ProgressCallback | None = None,
    progress_every: int = 5000,
) -> ResultadoEscritura:
    """Escribe en `destino` una copia de `plantilla` cuya hoja de formulas
    (`hoja`, o la primera) tiene el encabezado de la plantilla y, debajo, las
    `filas` (una lista de valores por posicion de columna: str, int, float o
    None/"" para celda vacia).

    `on_progress` recibe {escritas, total} cada `progress_every` filas y
    {guardando: True} antes de comprimir el libro."""
    plantilla, destino = Path(plantilla), Path(destino)
    tmp_dir = Path(tempfile.mkdtemp(prefix="tint_escritura_"))
    try:
        with zipfile.ZipFile(plantilla) as z:
            libro = _estructura(z)
            sheet_idx, sheet_name, sheet_part = _elegir_hoja(libro, hoja)
            sst_part = libro.shared_strings_part
            textos = _leer_shared_strings(z, sst_part)
            indice: dict[str, int] = {}
            for i, t in enumerate(textos):
                indice.setdefault(t, i)
            nuevos: list[str] = []

            with z.open(sheet_part) as f:
                lector = _LectorHoja(f)
                lector.abrir()
                filas_viejas = lector.filas()
                encabezado_xml = next(filas_viejas, None)
                if encabezado_xml is None:
                    raise FormatoExpertoError(f"la hoja '{sheet_name}' de {plantilla.name} no tiene encabezado")
                r_enc = _ROW_R_RE.search(encabezado_xml[: encabezado_xml.find(b">") + 1])
                fila_enc = int(r_enc.group(1)) if r_enc else 1
                estilos: dict[bytes, bytes] = {}
                refs_viejas = 0
                for n, fila in enumerate(filas_viejas):
                    if n == 0:
                        for m in _CELL_RE.finditer(fila):
                            r = _ATTR_R_RE.search(m.group(1))
                            s = _ATTR_S_RE.search(m.group(1))
                            if r and s:
                                estilos[r.group(1)] = s.group(1)
                    refs_viejas += fila.count(b't="s"')
                prefijo, sufijo = lector.prefijo, lector.sufijo

            letras: list[bytes] = []
            atributos: list[bytes] = []
            filas_tmp = tmp_dir / "filas.xml"
            ultima = fila_enc
            refs_nuevas = 0
            escritas = 0
            with open(filas_tmp, "wb", buffering=_CHUNK) as out:
                for valores in filas:
                    ultima += 1
                    escritas += 1
                    num = str(ultima).encode()
                    partes = [b'<row r="' + num + b'">']
                    for i, valor in enumerate(valores):
                        if valor is None or valor == "":
                            continue
                        while len(letras) <= i:
                            col = _col_letras(len(letras))
                            letras.append(col)
                            s = estilos.get(col)
                            atributos.append(b' s="' + s + b'"' if s else b"")
                        ref = letras[i] + num
                        if isinstance(valor, str) and sst_part is None:
                            partes.append(
                                b'<c r="' + ref + b'"' + atributos[i] + b' t="inlineStr"><is>' + _t(b"", valor)
                                + b"</is></c>"
                            )
                        elif isinstance(valor, str):
                            idx = indice.get(valor)
                            if idx is None:
                                idx = len(textos) + len(nuevos)
                                indice[valor] = idx
                                nuevos.append(valor)
                            partes.append(
                                b'<c r="' + ref + b'"' + atributos[i] + b' t="s"><v>' + str(idx).encode() + b"</v></c>"
                            )
                            refs_nuevas += 1
                        else:
                            partes.append(b'<c r="' + ref + b'"' + atributos[i] + b"><v>" + _numero(valor) + b"</v></c>")
                    partes.append(b"</row>")
                    out.write(b"".join(partes))
                    if on_progress is not None and escritas % progress_every == 0:
                        on_progress({"escritas": escritas, "total": total})

            if on_progress is not None:
                on_progress({"escritas": escritas, "total": total or escritas})
                on_progress({"guardando": True})

            num = str(ultima).encode()
            cabeza = _DIM_RE.sub(rb"\g<1>" + num + rb"\g<3>", prefijo, count=1) + encabezado_xml
            suf = _AUTOFILTER_RE.sub(rb"\g<1>" + num + rb"\g<3>", sufijo, count=1)
            reemplazos: dict[str, bytes | None] = {
                libro.workbook_part: _ajustar_workbook(z.read(libro.workbook_part), sheet_idx, ultima),
            }
            if sst_part is not None:
                reemplazos[sst_part] = _sst_con_nuevos(
                    z.read(sst_part), nuevos, len(textos) + len(nuevos), refs_nuevas - refs_viejas
                )
            destino.parent.mkdir(parents=True, exist_ok=True)
            _escribir_libro(z, destino, sheet_part, cabeza, filas_tmp, suf, reemplazos)
        return ResultadoEscritura(hoja=sheet_name, filas=escritas, textos_nuevos=len(nuevos))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
