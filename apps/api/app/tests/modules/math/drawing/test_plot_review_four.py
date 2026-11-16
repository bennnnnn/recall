"""The fourth review's look-alikes (2026-11-15), each now drawn as the question says.

A curve's domain is only one written to it ("f(x) = … for x ≥ 0", "defined for", "on [0, 2]"),
never a property it has on an interval or an area's interval. A tangent stands at each value
listed after "x =", at the place a word names (the y-axis, the origin), in the curve's own
letter. Rectangles of each rule the question names are drawn. A window shows a curve's start,
its rise and every root it marks, and one scale on both axes is the server's, sampled whole.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.modules.math.schemas.plot import PlotGraphSpec
from app.tests.modules.math.drawing.test_plot_review import _curve, _plot, _points_of, _shade


def _xs(graph: PlotGraphSpec) -> list[float]:
    return [x for segment in graph.curves[0].segments for x, _y in segment]


def _tangent(to: str, at: str, kind: str = "tangent") -> dict[str, Any]:
    return {"item": kind, "to": to, "at": at}


def _lines(graph: PlotGraphSpec | None) -> list[Any]:
    return [line for line in graph.lines if line.role == "line"] if graph else []


@pytest.mark.parametrize(
    ("question", "formula", "show", "low"),
    [
        (
            "Sketch y = x^2 - 5x + 6 and show that y < 0 when 2 < x < 3.",
            "x^2 - 5x + 6",
            "intercepts",
            2,
        ),
        (
            "Show that f(x) = x^3 - 3x is decreasing for -1 < x < 1, and sketch f.",
            "x^3 - 3x",
            "extrema",
            -1,
        ),
        (
            "Sketch f(x) = x^2 - 4x and explain why f is increasing for x > 2.",
            "x^2 - 4x",
            "extrema",
            2,
        ),
        (
            "Sketch y = x^2 - 4 and find the area under it for 0 ≤ x ≤ 3.",
            "x^2 - 4",
            "intercepts",
            0,
        ),
    ],
)
def test_a_property_or_an_area_interval_is_no_domain(
    question: str, formula: str, show: str, low: float
) -> None:
    """The curve runs on past the interval a property or an area is said on."""
    graph = _plot(question, _curve("f", formula), {"item": "points", "of": "f", "show": [show]})
    assert graph is not None and min(_xs(graph)) < low - 0.2


@pytest.mark.parametrize(
    ("question", "low", "high"),
    [
        ("The function f(x) = x^2 - 4x is defined for 0 ≤ x ≤ 3 only. Sketch f.", 0, 3),
        ("Sketch y = 1/x on [0.5, 2].", 0.5, 2),
        ("Let f: [0, 3] → R, f(x) = x^2. Sketch f.", 0, 3),
    ],
)
def test_a_domain_written_to_its_formula_is_drawn(question: str, low: float, high: float) -> None:
    formula = "1/x" if "1/x" in question else ("x^2 - 4x" if "4x" in question else "x^2")
    graph = _plot(question, _curve("f", formula))
    assert graph is not None
    xs = _xs(graph)
    assert min(xs) == pytest.approx(low, abs=1e-6) and max(xs) == pytest.approx(high, abs=1e-6)


def test_an_average_on_the_interval_beside_its_formula_draws_the_whole_curve() -> None:
    graph = _plot(
        "Find the average value of f(x) = x^2 on [0, 3] and show it on a graph.",
        _curve("f", "x^2"),
        {"item": "average", "of": "f", "from": "0", "to": "3"},
    )
    assert graph is not None and min(_xs(graph)) < 0


@pytest.mark.parametrize(
    "question",
    [
        "Find the area of the region under y = x^2 that lies between 1 and 3. Shade it.",
        "Evaluate ∫₁³ x² dx and shade the area it represents.",
        "Evaluate \\int_1^3 x^2 \\, dx and shade the region.",
    ],
)
def test_a_region_s_interval_is_read(question: str) -> None:
    graph = _plot(question, _curve("f", "x^2"), _shade("f", "x-axis", "1", "3"))
    assert graph is not None and any(region.kind == "shade" for region in graph.regions)


@pytest.mark.parametrize(
    ("question", "formula", "ats", "touching"),
    [
        (
            "Find the equations of the tangents to y = x^2 at the points where x = 1 and "
            "x = -2. Sketch them.",
            "x^2",
            ["1", "-2"],
            {(1.0, 1.0), (-2.0, 4.0)},
        ),
        (
            "Find the tangent to y = x^3 - 3x + 2 where the curve crosses the y-axis, and sketch it.",
            "x^3 - 3x + 2",
            ["0"],
            {(0.0, 2.0)},
        ),
        (
            "Find the tangent to y = x^3 + x at the origin and sketch it.",
            "x^3 + x",
            ["0"],
            {(0.0, 0.0)},
        ),
        ("Sketch y = x^2 and the tangent to it at (3, 9).", "x^2", ["3"], {(3.0, 9.0)}),
    ],
)
def test_a_tangent_stands_where_the_question_puts_it(
    question: str, formula: str, ats: list[str], touching: set[tuple[float, float]]
) -> None:
    graph = _plot(question, _curve("f", formula), *(_tangent("f", at) for at in ats))
    assert graph is not None and len(_lines(graph)) == len(ats)
    assert touching <= _points_of(graph)


def test_a_tangent_in_the_curve_s_own_letter() -> None:
    graph = _plot(
        "The position of a particle is s(t) = t^3 - 6t^2. Sketch s and the tangent at t = 2.",
        _curve("s", "t^3 - 6t^2"),
        _tangent("s", "2"),
    )
    assert graph is not None and len(_lines(graph)) == 1 and (2.0, -16.0) in _points_of(graph)


@pytest.mark.parametrize(
    ("question", "at"),
    [
        # A value listed after one said of a point is said of a point: no line x = 2.
        ("Find the gradient of y = x^3 when x = 1 and x = 2, and sketch the curve.", None),
        # "minutes" names no minimum, "across" no crossing: x = -1 is neither asked.
        (
            "A drone climbs for 10 minutes along y = x^3 - 3x. Sketch it and the tangent at x = 2.",
            "-1",
        ),
        ("Sketch y = x^2 - 4 across [-3, 3] and the tangent at x = 1.", "2"),
    ],
)
def test_a_word_inside_another_asks_for_no_place(question: str, at: str | None) -> None:
    formula = (
        "x^3" if "gradient" in question else ("x^2 - 4" if "x^2 - 4" in question else "x^3 - 3x")
    )
    items = (
        [_curve("f", formula), {"item": "line", "name": "L", "x": "2"}]
        if at is None
        else [
            _curve("f", formula),
            _tangent("f", at),
        ]
    )
    graph = _plot(question, *items)
    assert graph is not None and not _lines(graph)


@pytest.mark.parametrize(
    ("question", "drawn"),
    [
        (
            "Compare the left and right Riemann sums for f(x) = x^2 on [0, 2] with n = 4. Draw the rectangles.",
            {"left", "right"},
        ),
        (
            "Estimate the area under f(x) = x^2 on [0, 2] using left and right endpoints with n = 4.",
            {"left", "right"},
        ),
        ("Calculate L4 and R4 for f(x) = x^2 on [0, 2].", {"left", "right"}),
        (
            "Estimate the area under y = x^2 on [0, 2] using 4 rectangles with heights at the left "
            "endpoints. Explain whether the curve is increasing to the right.",
            {"left"},
        ),
    ],
)
def test_rectangles_of_each_rule_named_are_drawn(question: str, drawn: set[str]) -> None:
    for rule in ("left", "right", "midpoint"):
        rectangles = {
            "item": "rectangles",
            "under": "f",
            "from": "0",
            "to": "2",
            "n": 4,
            "rule": rule,
        }
        graph = _plot(question, _curve("f", "x^2"), rectangles)
        strips = [region for region in graph.regions if region.kind == "strip"] if graph else []
        assert bool(strips) == (rule in drawn), rule


def test_a_curve_described_as_its_real_value_draws() -> None:
    graph = _plot("Sketch y = (x^3)^(1/3).", _curve("f", "x"))
    assert graph is not None and min(_xs(graph)) < 0 < max(_xs(graph))


def test_a_window_shows_where_a_curve_starts_and_rises() -> None:
    start = _plot("Sketch y = ln(x)/sqrt(x^2 - 1).", _curve("f", "ln(x)/sqrt(x^2 - 1)"))
    assert start is not None and min(_xs(start)) == pytest.approx(1.0, abs=1e-3)
    power = _plot("Sketch y = x^x and find its minimum.", _curve("f", "x^x"))
    assert power is not None and power.x_min > -0.5 and max(_xs(power)) > 1.5


def test_a_line_and_the_curve_it_meets_are_seen_together() -> None:
    graph = _plot(
        "Sketch y = x^3 and the line x = 2.",
        _curve("f", "x^3"),
        {"item": "line", "name": "L", "x": "2"},
    )
    assert graph is not None and graph.y_max > 8


def test_every_root_in_view_is_marked() -> None:
    graph = _plot(
        "Sketch y = sin(5x) and mark where it crosses the x-axis.",
        _curve("f", "sin(5x)"),
        {"item": "points", "of": "f", "show": ["intercepts"]},
    )
    assert graph is not None
    step = math.pi / 5
    in_view = {round(k * step, 3) for k in range(-40, 41) if graph.x_min <= k * step <= graph.x_max}
    assert in_view == {round(p.x, 3) for p in graph.points if p.y == 0}


def test_one_scale_is_the_window_the_curves_are_sampled_on() -> None:
    graph = _plot(
        "Find the normal to y = x^2 at x = 1 and sketch it.",
        _curve("f", "x^2"),
        _tangent("f", "1", "normal"),
    )
    assert graph is not None and graph.equal
    assert (graph.x_max - graph.x_min) / (graph.y_max - graph.y_min) == pytest.approx(
        1.65, rel=1e-3
    )
    xs = _xs(graph)
    assert min(xs) == pytest.approx(graph.x_min, abs=1e-3) and max(xs) == pytest.approx(
        graph.x_max, abs=1e-3
    )
