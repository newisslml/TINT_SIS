from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tint_sis.canonical.models import FormulaCanonica

Severity = Literal["error", "warning"]


@dataclass
class ValidationIssue:
    severity: Severity
    mensaje: str
    linea_producto: str
    origen_archivo: str
    origen_fila: int


def validate_formula(formula: FormulaCanonica) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def _issue(severity: Severity, mensaje: str) -> None:
        issues.append(
            ValidationIssue(
                severity=severity,
                mensaje=mensaje,
                linea_producto=formula.linea_producto,
                origen_archivo=formula.origen_archivo,
                origen_fila=formula.origen_fila,
            )
        )

    if not formula.producto:
        _issue("error", "PRODUCTO vacio")
    if not formula.color:
        _issue("error", "COLOR vacio")
    if not formula.clasificacion:
        _issue("error", "Clasificacion vacia (falta metadata de la linea de producto)")

    for name, value in (("R", formula.r), ("G", formula.g), ("B", formula.b)):
        if value is not None and not (0 <= value <= 255):
            _issue("error", f"{name}={value} fuera de rango 0-255")

    if formula.oz_base is not None and formula.oz_base < 0:
        _issue("error", f"Oz Base negativo: {formula.oz_base}")

    if not formula.colorantes:
        _issue("warning", "formula sin colorantes")

    for colorante in formula.colorantes:
        if not colorante.codigo:
            _issue("error", "colorante con codigo vacio")
        if colorante.onzas_48 < 0:
            _issue("error", f"colorante {colorante.codigo}: cantidad negativa {colorante.onzas_48}")

    return issues


def validate_batch(formulas: list[FormulaCanonica]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for formula in formulas:
        issues.extend(validate_formula(formula))
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)
