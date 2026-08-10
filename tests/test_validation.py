from tint_sis.canonical.models import Colorante, FormulaCanonica
from tint_sis.validation.rules import has_errors, validate_formula


def _base_formula(**overrides) -> FormulaCanonica:
    data = dict(
        linea_producto="latex_experto",
        origen_archivo="x.xlsx",
        origen_fila=41,
        familia="Latex",
        clasificacion="1.-Latex",
        producto="Latex Experto",
        color="Blanco",
        r=255,
        g=255,
        b=255,
        colorantes=[Colorante(codigo="AM01", onzas_48=2.5)],
    )
    data.update(overrides)
    return FormulaCanonica(**data)


def test_valid_formula_has_no_errors():
    issues = validate_formula(_base_formula())
    assert not has_errors(issues)


def test_missing_producto_is_error():
    formula = _base_formula(producto="")
    issues = validate_formula(formula)
    assert has_errors(issues)
    assert any("PRODUCTO" in i.mensaje for i in issues)


def test_rgb_out_of_range_is_error():
    formula = _base_formula(r=300)
    issues = validate_formula(formula)
    assert has_errors(issues)


def test_missing_clasificacion_is_error():
    formula = _base_formula(clasificacion=None)
    issues = validate_formula(formula)
    assert has_errors(issues)


def test_negative_colorante_quantity_is_error():
    formula = _base_formula(colorantes=[Colorante(codigo="AM01", onzas_48=-1.0)])
    issues = validate_formula(formula)
    assert has_errors(issues)


def test_empty_colorantes_is_warning_not_error():
    formula = _base_formula(colorantes=[])
    issues = validate_formula(formula)
    assert not has_errors(issues)
    assert any("sin colorantes" in i.mensaje for i in issues)
