"""The fifth review's cases (2026-11-15): a domain in each notation a question writes it in,
the kinds of place a question asks for kept whole, ± read as two values, a tangent through a
point off the curve, and no point marked where the formula has no value."""

from __future__ import annotations

import time

import pytest

from app.tests.modules.math.drawing.test_plot_review import _curve, _plot, _points_of
from app.tests.modules.math.drawing.test_plot_review_four import _lines, _tangent, _xs


@pytest.mark.parametrize(
    ("question", "formula", "low", "high"),
    [
        ("Let f(x) = 2x + 1, 0 ≤ x ≤ 4. Sketch the graph of f.", "2x + 1", 0, 4),
        ("Sketch f(x) = x^2 - 4x with domain {x : 0 ≤ x ≤ 3}.", "x^2 - 4x", 0, 3),
        ("The function f: x ↦ x^2 - 1 has domain -2 ≤ x ≤ 2. Sketch it.", "x^2 - 1", -2, 2),
        ("Sketch the graph of y = x^2 for x between -1 and 2.", "x^2", -1, 2),
        ("Given f(x) = x^3, x ∈ [-1, 2], sketch f.", "x^3", -1, 2),
        ("A ball's height is h(t) = 20t - 5t^2 for 0 ≤ t ≤ 4. Sketch h.", "20t - 5t^2", 0, 4),
    ],
)
def test_a_domain_in_each_notation_is_read(
    question: str, formula: str, low: float, high: float
) -> None:
    graph = _plot(question, _curve("f", formula))
    assert graph is not None
    xs = _xs(graph)
    assert min(xs) == pytest.approx(low, abs=1e-6) and max(xs) == pytest.approx(high, abs=1e-6)
    assert all(not point.open for point in graph.points)


@pytest.mark.parametrize(
    ("question", "formula"),
    [
        ("Show that f(x) = x^3 - 3x is decreasing for -1 < x < 1, and sketch f.", "x^3 - 3x"),
        ("Sketch y = x^3 - 3x. It is concave up for x > 0.", "x^3 - 3x"),
        ("Sketch f(x) = x^2 - 4x, which is negative for 0 < x < 4.", "x^2 - 4x"),
        (
            "Sketch f(x) = x^2 - 4x; f is decreasing on (-∞, 2) and increasing on (2, ∞).",
            "x^2 - 4x",
        ),
        ("Sketch f(x) = x^2 - 4x, decreasing for x < 2.", "x^2 - 4x"),
        ("Sketch f(x) = x^3 - 12x, which is increasing for x < -2 and x > 2.", "x^3 - 12x"),
        ("Sketch f(x) = x^2 - 4x where f(x) < 0 for 0 < x < 4.", "x^2 - 4x"),
    ],
)
def test_a_property_in_any_wording_is_no_domain(question: str, formula: str) -> None:
    graph = _plot(question, _curve("f", formula))
    assert graph is not None and not graph.points
    assert min(_xs(graph)) < -0.3


def test_the_kinds_asked_for_are_kept_whole_under_the_cap() -> None:
    """Turning points asked for, bends not: past 24 points the bends go, the turns stay."""
    formula = "(sin(x) + cos(2x))/(1 + e^x)"
    show = ["extrema", "inflections", "intercepts"]
    graph = _plot(
        f"Sketch y = {formula} with its asymptotes and turning points.",
        _curve("f", formula),
        {"item": "points", "of": "f", "show": show},
    )
    assert graph is not None
    turns = {(-7.854, -1.999), (-6.031, 1.122), (-1.636, -1.665), (0.107, 0.513)}
    assert turns <= {(round(p.x, 3), round(p.y, 3)) for p in graph.points}


def test_plus_minus_is_two_places() -> None:
    graph = _plot(
        "Find the tangents to y = x^2 at x = ±1 and sketch them.",
        _curve("f", "x^2"),
        _tangent("f", "1"),
        _tangent("f", "-1"),
    )
    assert graph is not None and len(_lines(graph)) == 2


def test_a_tangent_through_a_point_off_the_curve() -> None:
    question = "Find the tangent to y = x^2 + 1 that passes through the origin, and sketch it."
    graph = _plot(question, _curve("f", "x^2 + 1"), _tangent("f", "1"), _tangent("f", "-1"))
    assert graph is not None and len(_lines(graph)) == 2
    assert {(1.0, 2.0), (-1.0, 2.0)} <= _points_of(graph)
    # The origin is off the curve: no tangent touches at its x.
    at_zero = _plot(question, _curve("f", "x^2 + 1"), _tangent("f", "0"))
    assert at_zero is not None and not _lines(at_zero)


@pytest.mark.parametrize("formula", ["(1 + 1/x)^x", "x^x", "0^x + x", "x^0"])
def test_no_point_where_the_formula_has_no_value(formula: str) -> None:
    """0⁰ and ∞⁰ are no 1: nothing is marked at 0, filled or labelled."""
    graph = _plot(
        f"Sketch y = {formula} and mark where it meets the axes.",
        _curve("f", formula),
        {"item": "points", "of": "f", "show": ["intercepts"]},
    )
    assert graph is not None
    assert not [p for p in graph.points if abs(p.x) < 1e-9 and not p.open]


@pytest.mark.wall_clock
def test_a_place_at_an_irrational_x_is_checked_at_once() -> None:
    """x^x's turn at 1/e, read as a ratio of ten-digit numbers, held SymPy for hours: a
    decimal is read as a fraction only when a small one is that close."""
    began = time.monotonic()
    graph = _plot(
        "Sketch y = x^x and find its minimum.",
        _curve("f", "x^x"),
        {"item": "points", "of": "f", "show": ["extrema", "inflections", "intercepts"]},
    )
    assert graph is not None and time.monotonic() - began < 5
    assert (0.368, 0.692) in _points_of(graph)
