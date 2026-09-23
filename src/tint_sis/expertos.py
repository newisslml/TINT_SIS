"""Definiciones de los archivos expertos y de los softwares que alimentan.

Hay 3 archivos expertos, cada uno en el formato que pide un grupo de softwares:

  Experto 1  Color Pro / Ibicus   Col.N-1/48 onzas = "AO-26.5" (codigo y cantidad juntos)
  Experto 2  Tintwise Lab (.xlsm) Col/Qty separados, cantidades ya en cm3
  Experto 3  Santint / Corob Tint colorant_N / qnt_ml_N en Oz/48

Ninguno trae un ID por formula y no estan alineados fila a fila (distintas filas,
orden y nombres de producto), asi que el cruce contra las tiendas se hace por
PRODUCTO: la tabla productos_TINT.xlsx (adapters/productos.py) dice que tiendas
lleva cada producto y como se llama en cada experto. Aca se define, por experto,
que columnas forman esa clave de producto (se ubican por encabezado, no por
posicion) y, por software, de que experto sale y que tiendas recibe.

En Experto 2 la columna "Clasificacion" viene desalineada respecto de "Producto"
(p.ej. "E.A. PF Biotech..." bajo "Latex"), por eso la clave es solo "Producto".
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Los grupos/tiendas se habilitan a mano una vez confirmado que la tabla de
# productos esta completa para ellos (no se adivina).
ENABLED_GRUPOS = {"MP14", "MP12", "Tiendas 14", "Tiendas 12"}

# Nombre fijo de la tabla de productos en la carpeta de entrada.
PRODUCTOS_NAME = "productos_TINT.xlsx"

# Carpeta (dentro de la salida) donde van las subcarpetas por software.
FILTRADOS_DIRNAME = "Archivos filtrados"

# Separador de las columnas que forman la clave cuando son mas de una (Experto 3:
# "Látex / Habitacional").
KEY_SEP = " / "


@dataclass(frozen=True)
class ExpertoDef:
    label: str  # tambien es el encabezado de su columna en productos_TINT.xlsx
    key_headers: tuple[str, ...]  # encabezados (normalizados) que forman la clave de producto
    default_glob: str


EXPERTOS: dict[str, ExpertoDef] = {
    d.label: d
    for d in (
        ExpertoDef("Experto 1", ("producto",), "Experto_1*.xlsx"),
        ExpertoDef("Experto 2", ("producto",), "Experto_2*.xls[xm]"),
        ExpertoDef("Experto 3", ("group_code", "product_code"), "Experto_3*.xlsx"),
    )
}


@dataclass(frozen=True)
class SoftwareDef:
    nombre: str  # tambien es el nombre de su carpeta de salida
    experto: str  # label de EXPERTOS
    tiendas: tuple[str, ...]
    formato: str  # "excel" (misma extension que el experto: .xlsx/.xlsm) | "csv"

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "experto": self.experto,
            "tiendas": list(self.tiendas),
            "formato": self.formato,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SoftwareDef":
        formato = str(data["formato"]).strip().lower()
        if formato not in FORMATOS:
            raise ValueError(f"formato '{formato}' no soportado (usar {', '.join(sorted(FORMATOS))})")
        return cls(
            nombre=str(data["nombre"]).strip(),
            experto=str(data["experto"]).strip(),
            tiendas=tuple(str(t) for t in data["tiendas"]),
            formato=formato,
        )


FORMATOS = {"excel", "csv"}

_TODAS = ("Tiendas 14", "Tiendas 12", "MP12", "MP14")

SOFTWARES_DEFAULT: tuple[SoftwareDef, ...] = (
    SoftwareDef("Santint", "Experto 3", ("Tiendas 14",), "excel"),
    SoftwareDef("Corob_Tint", "Experto 3", _TODAS, "excel"),
    SoftwareDef("Tinwise_Lab", "Experto 2", ("Tiendas 14",), "excel"),
    SoftwareDef("Color_Pro3.1.1", "Experto 1", _TODAS, "csv"),
    SoftwareDef("Color_Pro4.8", "Experto 1", ("Tiendas 14",), "excel"),
    SoftwareDef("Ibicus_Spa", "Experto 1", ("Tiendas 14",), "excel"),
)


_ESPACIOS_RE = re.compile(r"\s+")


def normalizar(valor: object) -> str:
    """Forma canonica para comparar nombres de producto entre la tabla y los
    expertos: sin acentos, sin mayusculas y sin espacios (los expertos escriben
    distinto el mismo producto: "Ltx. Extracubriente Sipa" vs
    "Ltx.Extracubriente Sipa")."""
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return _ESPACIOS_RE.sub("", texto).casefold()


def clave_visible(valores: list[object] | tuple[object, ...]) -> str:
    """Clave legible (la que se escribe en la tabla / advertencias) a partir de
    los valores de las columnas clave de una fila."""
    partes = ["" if v is None else str(v).strip() for v in valores]
    return KEY_SEP.join(partes)


def clave_normalizada(valores: list[object] | tuple[object, ...]) -> str:
    return normalizar(clave_visible(valores))
