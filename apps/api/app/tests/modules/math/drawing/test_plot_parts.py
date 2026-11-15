"""The parts a graph is drawn from: the real branch, a curve's places and breaks, labels.

Round 3 (2026-11-14): x^(1/3)(x + 3)^(2/3) lost its cusp and (x² - 4)^(2/3) drew a flat
line across [-2, 2], numpy taking no real root of a negative; a curve was joined across its
asymptote; |x² - 1| and x²|9 - x²| were read as other formulas. Each check here holds one
part to values worked by hand.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from sympy import E, Rational, Symbol, exp, pi, sqrt

from app.modules.math.drawing.curve_breaks import breaks, end_lines
from app.modules.math.drawing.curve_features import bends, exact_xs, turning_points, zeros
from app.modules.math.drawing.plot_labels import formula_text, number_text
from app.modules.math.drawing.plot_question import plain, read_plot_question
from app.modules.math.drawing.real_curve import RealFunction, X, as_real
from app.modules.math.tool_check import parse_formula

_x = Symbol("x")


def _fn(text: str) -> RealFunction:
    return RealFunction(as_real(parse_formula(text), _x))


@pytest.mark.parametrize(
    ("formula", "x", "y"),
    [
        ("x^(1/3)", -8, -2.0),
        ("x^(2/3)", -8, 4.0),
        ("x^(1/3)*(x + 3)^(2/3)", -4, -(4 ** (1 / 3))),
        ("(x^2 - 4)^(2/3)", 0, 16 ** (1 / 3)),
        ("sqrt(x)", -1, math.nan),
    ],
)
def test_odd_roots_of_negatives_are_real(formula: str, x: float, y: float) -> None:
    found = _fn(formula).at(x)
    assert (math.isnan(found) and math.isnan(y)) or found == pytest.approx(y)


@pytest.mark.parametrize(
    ("formula", "low", "high", "turns"),
    [
        # A cusp, a smooth minimum, and a corner, found alike.
        ("x^(1/3)*(x + 3)^(2/3)", -6, 4, [-3.0, -1.0]),
        ("(x^2 - 4)^(2/3)", -5, 5, [-2.0, 0.0, 2.0]),
        ("abs(ln(x))", 0.01, 5, [1.0]),
        ("x^4 - 8x^2 + 6", -5, 5, [-2.0, 0.0, 2.0]),
    ],
)
def test_turning_points_take_in_cusps_and_corners(
    formula: str, low: float, high: float, turns: list[float]
) -> None:
    found = turning_points(_fn(formula).values, low, high)
    assert found == pytest.approx(turns, abs=1e-6)


def test_a_pole_is_no_root_and_a_touch_is_one() -> None:
    assert zeros(_fn("1/x").values, -3, 3) == []
    assert zeros(_fn("x^4 - x^2").values, -2, 2) == pytest.approx([-1, 0, 1], abs=1e-6)


def test_an_inflection_with_a_vertical_tangent_is_found() -> None:
    assert bends(_fn("x^(1/3)*(x + 3)^(2/3)"), -6, 4) == pytest.approx([0.0], abs=1e-6)
    assert bends(_fn("ln(x)/x"), 0.01, 10) == pytest.approx([float(exp(Rational(3, 2)))])


@pytest.mark.parametrize(
    ("formula", "at", "left", "right"),
    [
        ("(x^2 - 2x + 4)/(x - 2)", 2, "infinite", "infinite"),
        ("4abs(x^2 - 1)/(x - 1)", 1, "finite", "finite"),
        ("(x^2 + x - 20)/(x^2 + 4x - 5)", -5, "finite", "finite"),
        ("ln(x)/x", 0, "none", "infinite"),
    ],
)
def test_a_break_is_told_by_its_sides(formula: str, at: float, left: str, right: str) -> None:
    fn = _fn(formula)
    found = [b for b in breaks(fn, -10, 10, exact_xs(fn)) if abs(float(b.x) - at) < 1e-9]
    assert len(found) == 1 and (found[0].left.kind, found[0].right.kind) == (left, right)


@pytest.mark.parametrize(
    ("formula", "lines"),
    [
        ("(x^2 - 2x + 4)/(x - 2)", [(1, 0)]),
        ("x^(1/3)*(x + 3)^(2/3)", [(1, 2)]),
        ("x*exp(x) - 4", [(0, -4)]),
        ("x^2", []),
    ],
)
def test_end_lines_are_sympys(formula: str, lines: list[tuple[int, int]]) -> None:
    assert end_lines(_fn(formula)) == lines


@pytest.mark.parametrize(
    ("value", "text"),
    [(Rational(-1, 2), "−1/2"), (sqrt(5), "√5"), (pi / 4, "π/4"), (exp(-1), "1/e"),
     (E, "e"), (-2 * sqrt(3) / 3, "−1.15"), (Rational(1, 300), "0.003")],
)  # fmt: skip
def test_a_value_is_exact_when_short(value: object, text: str) -> None:
    assert number_text(value) == text


def test_a_formula_reads_as_a_question_writes_it() -> None:
    assert formula_text(9 - X**2) == "9 − x²"
    assert formula_text(X**2 - 5 * X + 1) == "x² − 5x + 1"


def test_bars_superscripts_and_roots_read_plainly() -> None:
    assert plain("f(x) = x²|9 − x²|/(3 − x)") == "f(x) = x^(2)abs(9 - x^(2))/(3 - x)"
    assert plain("y = √x and eˣ") == "y = sqrt(x) and e^(x)"
    question = read_plot_question(["Let v(t) = t² − 4t + 3 m/s for 0 ≤ t ≤ 4."])
    assert [str(w.expr) for w in question.formulas if w.name == "v"] == ["t**2 - 4*t + 3"]
    assert sorted(float(v) for v in question.x_values) == [0.0, 4.0]


def test_a_sample_runs_through_its_turning_point() -> None:
    xs = np.linspace(-1, 1, 5)
    assert np.all(np.isfinite(_fn("x^(2/3)").values(xs)))
