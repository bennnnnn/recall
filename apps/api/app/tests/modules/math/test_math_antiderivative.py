"""An indefinite integral's card: the textbook form, checked, and never a complex branch."""

from __future__ import annotations

import pytest
from sympy import I, Piecewise, Rational, Symbol, diff, parse_expr

from app.modules.math import solve as math_solve
from app.modules.math.solve.parse import parse_expression

X = Symbol("x", real=True)
# Real points where every integrand below is real and finite.
POINTS = (Rational(43, 10), Rational(61, 10), Rational(97, 10))


@pytest.mark.parametrize(
    ("integrand", "shown"),
    [
        # integrate() gave a Piecewise with an i branch for these: the substitution form.
        (
            "(x + 2)*sqrt(x - 3)",
            r"\frac{2 \left(x - 3\right)^{\frac{3}{2}} \left(3 x + 16\right)}{15}",
        ),
        ("sqrt(x - 1)/x", r"2 \sqrt{x - 1} - 2 \arctan{\left(\sqrt{x - 1} \right)}"),
        ("x/sqrt(x - 5)", None),
        ("x*sqrt(x - 1)", None),
        ("x*(x - 4)^(1/3)", None),
        # A table result, not SymPy's rewrite of it: -cot x, not -1/tan x.
        ("csc(x)^2", r"- \cot{\left(x \right)}"),
        ("sec(x)^2", r"\tan{\left(x \right)}"),
        # Substitution keeps the power: not a degree-6 polynomial over 3.
        ("(2*x + 1)^5", r"\frac{\left(2 x + 1\right)^{6}}{12}"),
        ("x^2*sqrt(x^3 + 1)", r"\frac{2 \left(x^{3} + 1\right)^{\frac{3}{2}}}{9}"),
        ("x*cos(x)", None),
        # The rule-based answer, ln(2x⁴ + 4x² + 2)/4 + ..., is longer: integrate()'s stands.
        (
            "x^3/(x^2 + 1)^2",
            r"\frac{\left(x^{2} + 1\right) \ln{\left(x^{2} + 1 \right)} + 1}{2 \left(x^{2} + 1\right)}",
        ),
        ("1/x", r"\ln\left|x\right|"),
    ],
)
def test_integrate_expression_gives_the_textbook_form(integrand: str, shown: str | None) -> None:
    result = math_solve.integrate_expression(integrand, "x")
    assert result.solved is True
    antiderivative = parse_expr(result.result, {"x": X})
    assert not antiderivative.has(I) and not antiderivative.has(Piecewise)
    function = parse_expression(integrand, ["x"]).subs(Symbol("x"), X)
    for point in POINTS:
        assert abs(complex((diff(antiderivative, X) - function).subs(X, point).evalf())) < 1e-9
    if shown is not None:
        assert result.latex == shown


@pytest.mark.parametrize(
    "integrand",
    [
        # Only integrate() closes it, with an i branch for |x| < 1; the rule-based answer's
        # Piecewise names the wrong domain. Neither is a card a student can use.
        "sqrt(x^2 - 1)/x",
        # A hypergeometric function of exp_polar(i pi) x³: right, and no school answer.
        "sqrt(1 + x^3)",
    ],
)
def test_integrate_expression_withholds_a_complex_form(integrand: str) -> None:
    assert math_solve.integrate_expression(integrand, "x").solved is False


def test_integrate_expression_keeps_a_parameter_piecewise() -> None:
    # ∫ xⁿ dx is xⁿ⁺¹/(n + 1) for n ≠ -1 and ln x otherwise: the whole answer, still a card.
    result = math_solve.integrate_expression("x^n", "x")
    assert result.solved is True
    assert "n + 1" in result.result


@pytest.mark.parametrize(
    "integrand",
    [
        # The rule-based search took 1-5 s on each of these, past the solve's time limit.
        "x^5/(x^2 + 1)^3",
        "1/(x*(x^2 + 1)^2)",
        "x^2/(x^3 + 1)^2",
        "1/((x - 1)^2*(x + 1)^2)",
        "(x^2 + 2)/((x + 1)^2*(x - 2))",
        "x/(x^2 + 1)",
    ],
)
def test_a_fraction_of_polynomials_takes_integrates_partial_fractions(
    integrand: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sympy.integrals.manualintegrate as manual

    def never(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the rule-based search ran on a fraction of polynomials")

    monkeypatch.setattr(manual, "manualintegrate", never)
    result = math_solve.integrate_expression(integrand, "x")
    assert result.solved is True
    antiderivative = parse_expr(result.result, {"x": X})
    function = parse_expression(integrand, ["x"]).subs(Symbol("x"), X)
    for point in POINTS:
        assert abs(complex((diff(antiderivative, X) - function).subs(X, point).evalf())) < 1e-9


def test_a_rule_based_answer_with_an_i_is_never_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import sympy.integrals.manualintegrate as manual
    from sympy import cos, exp, sin

    # sin x written through e^(ix): right, and no answer a school card shows.
    monkeypatch.setattr(
        manual, "manualintegrate", lambda *_a, **_k: (exp(I * X) - exp(-I * X)) / (2 * I)
    )
    from app.modules.math.solve.antiderivative import textbook_antiderivative

    assert textbook_antiderivative(cos(X), X) == sin(X)
