"""The sixth review's cases (2026-11-16): a condition that opens a clause is no domain, a
tangent through a point only where the question ties them, and no description that holds the
drawing past its budget."""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.tests.modules.math.drawing.test_plot_review import _curve, _plot
from app.tests.modules.math.drawing.test_plot_review_four import _lines, _tangent, _xs


@pytest.mark.parametrize(
    ("question", "formula", "low"),
    [
        (
            "For f(x) = x^2 - 4x, when x < 2, is f increasing or decreasing? Sketch f.",
            "x^2 - 4x",
            2,
        ),
        ("Sketch y = x^2 - 4x, for x between 4 and 5 the curve is above the axis.", "x^2 - 4x", 4),
        ("Sketch y = x^2 - 4, where x > 0 gives the positive root.", "x^2 - 4", 0),
        ("Sketch y = x^2 - 4x; is y > 0 for x between 4 and 5?", "x^2 - 4x", 4),
    ],
)
def test_a_condition_that_opens_a_clause_is_no_domain(
    question: str, formula: str, low: float
) -> None:
    graph = _plot(question, _curve("f", formula))
    assert graph is not None and min(_xs(graph)) < low - 0.2 and not graph.points


@pytest.mark.parametrize(
    ("question", "formula", "low"),
    [
        ("Use the graph of f(x) = e^x - 2, for x > 0 to estimate the root.", "e^x - 2", 0),
        ("Sketch y = x^2 for 0 ≤ x ≤ 3 and shade the area from 1 to 3.", "x^2", 0),
        ("Given f(x) = x^3, x ∈ [-1, 2], sketch f.", "x^3", -1),
    ],
)
def test_a_condition_that_closes_the_formula_is_its_domain(
    question: str, formula: str, low: float
) -> None:
    graph = _plot(question, _curve("f", formula))
    assert graph is not None and min(_xs(graph)) == pytest.approx(low, abs=1e-6)


@pytest.mark.parametrize(
    ("question", "at"),
    [
        ("Sketch y = e^x and its tangent at x = 0. Mark the origin.", "1"),
        ("Sketch y = x^2 and the tangent at x = 1. Also plot the point (3, 0).", "6"),
    ],
)
def test_a_point_stated_for_another_reason_places_no_tangent(question: str, at: str) -> None:
    formula = "e^x" if "e^x" in question else "x^2"
    graph = _plot(question, _curve("f", formula), _tangent("f", at))
    assert graph is not None and not _lines(graph)


def test_tangents_from_a_point_the_question_ties_them_to() -> None:
    graph = _plot(
        "Find the tangents from the point (1, -3) to y = x^2 and sketch them.",
        _curve("f", "x^2"),
        _tangent("f", "3"),
        _tangent("f", "-1"),
    )
    assert graph is not None and len(_lines(graph)) == 2


_SLOW: list[tuple[str, list[dict[str, Any]]]] = [
    (
        "Sketch y = (x^5 - x - 3)^(3/5)/(x^3 - 2x - 5).",
        [_curve("f", "(x^5 - x - 3)^(3/5)/(x^3 - 2x - 5)")],
    ),
    (
        "Sketch y = (x^7 - 3x^5 + x - 9)^(2/3)/(x^4 + x - 1) with asymptotes.",
        [
            _curve("f", "(x^7 - 3x^5 + x - 9)^(2/3)/(x^4 + x - 1)"),
            {"item": "asymptotes", "of": "f"},
            {"item": "points", "of": "f", "show": ["extrema", "inflections", "intercepts"]},
        ],
    ),
    (
        "Sketch y = (x^2 + 1)^(1/3) sin(x)^(7/3) and its asymptotes.",
        [_curve("f", "(x^2 + 1)^(1/3) sin(x)^(7/3)"), {"item": "asymptotes", "of": "f"}],
    ),
    ("Sketch y = x^x^x and mark its turning points.", [_curve("f", "x^x^x")]),
    ("Sketch y = ln(ln(ln(x))) and its asymptotes.", [_curve("f", "ln(ln(ln(x)))")]),
    (
        "Average of f(x) = e^(x^2) sin(x^3) on [0, 2]",
        [_curve("f", "e^(x^2) sin(x^3)"), {"item": "average", "of": "f", "from": "0", "to": "2"}],
    ),
    ("Sketch y = x^(1/x) and its tangent at x = e.", [_curve("f", "x^(1/x)"), _tangent("f", "e")]),
]


@pytest.mark.wall_clock
@pytest.mark.parametrize(("question", "items"), _SLOW)
def test_a_hard_formula_draws_within_the_budget(question: str, items: list[dict[str, Any]]) -> None:
    """Production gives drawing the solve timeout (5 s): a hole SymPy's limit took nine
    seconds to rule out at a cubic's radical root drew nothing."""
    began = time.monotonic()
    graph = _plot(question, *items)
    assert graph is not None and time.monotonic() - began < 4


def test_an_equation_solved_graphically_draws_its_sides() -> None:
    """ "Use graphing to solve x² = 4": y = x² and y = 4, meeting at x = ±2 (the live round
    drew nothing, the equation being no "y =" the question wrote)."""
    graph = _plot(
        "Use graphing to solve x^2 = 4.",
        _curve("f", "x^2"),
        {"item": "line", "name": "L", "y": "4"},
        {"item": "points", "of": "f", "show": ["crossings"]},
    )
    assert graph is not None and len(graph.lines) == 1
    assert {(round(p.x, 3), round(p.y, 3)) for p in graph.points} == {(-2.0, 4.0), (2.0, 4.0)}
    difference = _plot("Solve x^2 - 4 = 0 graphically.", _curve("f", "x^2 - 4"))
    assert difference is not None and difference.curves


def test_a_place_of_two_kinds_stays_while_one_is_asked() -> None:
    """sin 5x's roots are its bends too: past the cap the bends go, the asked roots stay."""
    graph = _plot(
        "f(x) = x^2 if x < 1, and f(x) = x + 3 if x >= 1. Sketch f and y = sin(5x), and "
        "mark where y = sin(5x) crosses the x-axis.",
        _curve("f", pieces=[{"y": "x^2", "when": "x < 1"}, {"y": "x + 3", "when": "x >= 1"}]),
        _curve("g", "sin(5x)"),
        {"item": "points", "of": "g", "show": ["intercepts", "extrema", "inflections"]},
    )
    assert graph is not None
    marked = {(round(p.x, 3), round(p.y, 3), p.open) for p in graph.points}
    assert (1.0, 1.0, True) in marked and (1.0, 4.0, False) in marked
    # The roots asked for stay whole, though each is a bend too.
    assert {(0.628, 0.0, False), (-0.628, 0.0, False), (3.142, 0.0, False)} <= marked


def test_a_jump_s_circles_are_never_cut_by_the_cap() -> None:
    """24 marked places and a jump: the cap is counted after the curve's own circles, which
    stay (PR #2468 review: the last slice cut the jump's open circle)."""
    from app.modules.math.drawing.plot_curves import add_curves
    from app.modules.math.drawing.plot_draw import draw_plot
    from app.modules.math.drawing.plot_items import Curve
    from app.modules.math.drawing.plot_question import read_plot_question
    from app.modules.math.drawing.plot_scene import DrawnPoint, Scene

    question = read_plot_question(["f(x) = x^2 if x < 1, and f(x) = x + 3 if x >= 1."])
    scene = Scene(asked=("roots",))
    pieces = [{"y": "x^2", "when": "x < 1"}, {"y": "x + 3", "when": "x >= 1"}]
    add_curves(
        [Curve.model_validate({"item": "curve", "name": "f", "pieces": pieces})], question, scene
    )
    for i in range(24):
        scene.add_point(DrawnPoint(-3 + 0.2 * i, 9.0, kinds=frozenset({"roots"})))
    graph = draw_plot(scene)
    assert graph is not None and len(graph.points) <= 24
    marked = {(round(p.x, 3), round(p.y, 3), p.open) for p in graph.points}
    assert (1.0, 1.0, True) in marked and (1.0, 4.0, False) in marked


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0 <= x != 1 < 3", {(">=", 0), ("<", 3), ("!=", 1)}),
        ("-5 < x != 1", {(">", -5), ("!=", 1)}),
        ("x != -1/2", {("!=", -0.5)}),
    ],
)
def test_an_excluded_value_keeps_the_bounds_around_it(
    text: str, expected: set[tuple[str, float]]
) -> None:
    from app.modules.math.drawing.plot_reading import conditions

    assert {(c.op, float(c.value)) for c in conditions(text)} == expected
