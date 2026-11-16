"""The wrong pictures the 2026-11-15 review drew from look-alike descriptions, each now left out.

Each case is a question and a ```draw description a reply might write. A picture may lack
what does not check; it never shows what is not so: a value the question gives as a curve,
an antiderivative standing in for f, a region bounded by a number said of something else or
across a pole, a tangent at a corner or a jump, an asymptote that is the curve itself,
rectangles for the trapezoidal rule, an axis of revolution the question does not turn about,
an open circle where a piece left out has its value.
"""

from __future__ import annotations

import json
import math
import time
from typing import Any

import pytest

from app.modules.math.drawing.build import drawn_fence
from app.modules.math.schemas.plot import PlotGraphSpec


def _plot(question: str, *items: dict[str, Any], reply: str = "") -> PlotGraphSpec | None:
    body = json.dumps({"kind": "plot", "items": list(items)})
    fence = drawn_fence(body, [question], reply)
    if fence is None:
        return None
    return PlotGraphSpec.model_validate_json(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])


def _curve(name: str, y: str | None = None, **more: Any) -> dict[str, Any]:
    return {"item": "curve", "name": name, **({"y": y} if y else {}), **more}


def _shade(
    first: str, second: str, start: str | None = None, end: str | None = None
) -> dict[str, Any]:
    ends = {"from": start, "to": end} if start is not None else {}
    return {"item": "shade", "between": [first, second], **ends}


_PIECES = [{"y": "x^2", "when": "x < 1"}, {"y": "x + 3", "when": "x >= 1"}]
_CORNER = [{"y": "x", "when": "x < 1"}, {"y": "2 - x", "when": "x >= 1"}]


@pytest.mark.parametrize(
    ("question", "items"),
    [
        # W2: "a = 3" is a value, never the line y = 3.
        ("Let a = 3. Find the area under y = x^2 from x = 0 to x = a.", [_curve("a", "3")]),
        # W1: x² is no picture of f(x) = 2x unless antiderivatives are asked for.
        ("Given f(x) = 2x, find the area under f from x = 0 to x = 3.", [_curve("f", "x^2")]),
    ],
)
def test_a_curve_the_question_does_not_draw_is_left_out(
    question: str, items: list[dict[str, Any]]
) -> None:
    graph = _plot(question, _curve("f", "x^2"), *items)
    labels = [curve.label for curve in graph.curves] if graph else []
    assert "y = 3" not in labels and len(labels) <= 1


@pytest.mark.parametrize(
    ("question", "items"),
    [
        # W3: 3 is where a gradient is asked, and "between 2 and 3" is said of the answer.
        (
            "Find the area enclosed by y = x^2 and y = x + 2. Then find the gradient of the "
            "parabola at x = 3. Shade the region.",
            [_curve("g", "x + 2"), _shade("f", "g", "-1", "3")],
        ),
        (
            "Find the area under y = x^2 from x = 0 to x = 2 and check that your answer is "
            "between 2 and 3. Shade it.",
            [_shade("f", "x-axis", "0", "3")],
        ),
        # W3: sin x and cos x meet without end; no bounds bound nothing.
        (
            "Find the area enclosed by y = sin x and y = cos x between two consecutive "
            "intersections. Shade it.",
            [_curve("g", "cos(x)"), _shade("g", "s")],
        ),
        # W4: across a pole.
        (
            "Find the area under y = 1/x^2 from x = -1 to x = 1 and shade it.",
            [_curve("p", "1/x^2"), _shade("p", "x-axis", "-1", "1")],
        ),
        # W8: the trapezoidal rule, and a width the count must hold to.
        (
            "Use the trapezoidal rule with n = 4 to approximate the integral of x^2 from "
            "x = 0 to x = 2. Sketch the approximation.",
            [{"item": "rectangles", "under": "f", "from": "0", "to": "2", "n": 4, "rule": "left"}],
        ),
        (
            "The region under y = x^2 from x = 0 to x = 2 is split into rectangles of width "
            "0.5 using left endpoints. Draw them; there are 3 people in my group.",
            [{"item": "rectangles", "under": "f", "from": "0", "to": "2", "n": 3, "rule": "left"}],
        ),
    ],
)
def test_a_region_the_question_does_not_bound_is_left_out(
    question: str, items: list[dict[str, Any]]
) -> None:
    first = _curve("s", "sin(x)") if "sin" in question else _curve("f", "x^2")
    graph = _plot(question, first, *items)
    assert graph is None or not graph.regions


def test_a_three_edge_region_is_the_one_all_three_enclose() -> None:
    """W5: the region under 2 - x across [0, 2] had y = x² running through it."""
    graph = _plot(
        "Find the area enclosed by y = x^2, y = 2 - x and the x-axis for x >= 0. Shade it.",
        _curve("f", "x^2"),
        _curve("g", "2 - x"),
        {"item": "shade", "between": ["f", "g", "x-axis"]},
    )
    assert graph is not None and graph.regions
    xs = [x for region in graph.regions for x, _y in region.points]
    ys = [y for region in graph.regions for _x, y in region.points]
    assert min(xs) >= -1e-9 and max(xs) <= 2 + 1e-9 and max(ys) <= 1 + 1e-6


@pytest.mark.parametrize(
    ("question", "curve", "at"),
    [
        ("Let f(x) = |x - 2|. Sketch f and the tangent at x = 2.", _curve("f", "|x - 2|"), "2"),
        ("Sketch f(x) = |x^2 - 4| and the tangent at x = 2.", _curve("f", "|x^2 - 4|"), "2"),
        ("Sketch y = x^(2/3) and the tangent at x = 0.", _curve("f", "x^(2/3)"), "0"),
        (
            "Let f(x) = x if x < 1; f(x) = 2 - x if x >= 1. Sketch f and its tangent at x = 1.",
            _curve("f", pieces=_CORNER),
            "1",
        ),
        (
            "Let f(x) = x^2 if x < 1; f(x) = x + 3 if x >= 1. Sketch f and the tangent at x = 1.",
            _curve("f", pieces=_PIECES),
            "1",
        ),
    ],
)
def test_no_tangent_where_the_curve_has_none(question: str, curve: dict[str, Any], at: str) -> None:
    """W6: a corner, a cusp and a jump have no one tangent, and no normal."""
    touching = [{"item": kind, "to": "f", "at": at} for kind in ("tangent", "normal")]
    graph = _plot(question, curve, *touching)
    assert graph is None or not [line for line in graph.lines if line.role == "line"]


@pytest.mark.parametrize(
    ("question", "formula"),
    [
        ("Sketch f(x) = (x^2 - 1)/(x - 1) and show any asymptotes.", "(x^2 - 1)/(x - 1)"),
        ("Sketch y = 2x + 1 and show any asymptotes.", "2x + 1"),
        ("Sketch y = 3 and show its asymptotes.", "3"),
    ],
)
def test_a_curve_is_never_its_own_asymptote(question: str, formula: str) -> None:
    """W7."""
    graph = _plot(question, _curve("f", formula), {"item": "asymptotes", "of": "f"})
    assert graph is not None and not [line for line in graph.lines if line.role == "asymptote"]


@pytest.mark.parametrize(
    ("question", "axis"),
    [
        (
            "The region bounded by y = x^2, the x-axis and x = 2 is rotated about the y-axis. "
            "Find the volume and show the region and the axis.",
            "x-axis",
        ),
        (
            "The region bounded by y = x^2 and y = 4 is rotated about the line y = -1. "
            "Find the volume and show the axis.",
            "y = 4",
        ),
    ],
)
def test_the_axis_is_the_one_after_about(question: str, axis: str) -> None:
    """W9: a boundary the question mentions is no axis of revolution."""
    graph = _plot(
        question,
        _curve("f", "x^2"),
        _shade("f", "x-axis", "0", "2"),
        {"item": "axis", "line": axis},
        {"item": "slice", "method": "disc"},
    )
    assert graph is not None
    assert not [line for line in graph.lines if line.role == "axis"]
    assert not [region for region in graph.regions if region.kind != "shade"]


def test_an_average_across_a_pole_is_left_out() -> None:
    """W4: the average of 1/(x - 1) on [0, 3] was drawn at -0.374."""
    graph = _plot(
        "Find the average value of f(x) = 1/(x - 1) on [0, 3] and show it.",
        _curve("f", "1/(x - 1)"),
        {"item": "average", "of": "f", "from": "0", "to": "3"},
    )
    assert graph is not None and not graph.lines


def _true_to(graph: PlotGraphSpec, fn: Any) -> bool:
    """Every point drawn is the curve's own, to a hundredth of the window's height: no
    staircase of rounded coordinates (j01, j02)."""
    height = graph.y_max - graph.y_min
    points = [point for segment in graph.curves[0].segments for point in segment]
    return all(
        abs(y - fn(x)) <= 0.01 * height for x, y in points if graph.y_min <= y <= graph.y_max
    )


def test_a_curve_is_drawn_at_its_own_scale() -> None:
    """W10: tan x within a readable height, x² on [0, 0.001] no flat line, and sin 50x on
    the whole interval asked."""
    tan = _plot("Sketch y = tan x.", _curve("f", "tan(x)"))
    assert tan is not None and max(abs(tan.y_min), abs(tan.y_max)) < 50
    tiny = _plot("Sketch y = x^2 on [0, 0.001].", _curve("f", "x^2", domain=["0", "0.001"]))
    assert tiny is not None and _true_to(tiny, lambda x: x * x)
    huge = _plot("Sketch y = e^x on [0, 20].", _curve("f", "e^x", domain=["0", "20"]))
    assert huge is not None and _true_to(huge, math.exp)
    waves = _plot("Sketch y = sin(50x) on [0, 2pi].", _curve("f", "sin(50x)", domain=["0", "2pi"]))
    assert waves is not None
    xs = [x for s in waves.curves[0].segments for x, _y in s]
    assert min(xs) < 0.01 and max(xs) > 2 * math.pi - 0.01


def test_no_open_circle_where_a_piece_left_out_has_its_value() -> None:
    """W11: the middle piece (b x², b unread) left out left an open circle at (2, 4)."""
    graph = _plot(
        "Find a and b so that f is continuous: f(x) = x^3 + a if x < 1; f(x) = b x^2 if "
        "1 <= x <= 2; f(x) = 4x - 4 if x > 2. Sketch f.",
        _curve(
            "f",
            pieces=[
                {"y": "x^3 + 3", "when": "x < 1"},
                {"y": "x^2", "when": "1 <= x <= 2"},
                {"y": "4x - 4", "when": "x > 2"},
            ],
        ),
    )
    assert graph is None or not [point for point in graph.points if point.open]


def test_turning_points_asked_for_stay_beside_a_region() -> None:
    graph = _plot(
        "Sketch f(x) = x^3 - 3x, mark its turning points, and shade the area under f from "
        "x = 2 to x = 3.",
        _curve("f", "x^3 - 3x"),
        {"item": "points", "of": "f", "show": ["extrema"]},
        _shade("f", "x-axis", "2", "3"),
    )
    assert graph is not None
    assert {(round(p.x), round(p.y)) for p in graph.points} >= {(-1, 2), (1, -2)}


@pytest.mark.wall_clock
def test_an_average_with_no_closed_form_is_quick() -> None:
    began = time.monotonic()
    graph = _plot(
        "Find the average value of f(x) = e^(x^2)/(1 + x^4) on [0, 2] and show it.",
        _curve("f", "e^(x^2)/(1 + x^4)"),
        {"item": "average", "of": "f", "from": "0", "to": "2"},
    )
    assert graph is not None and graph.lines and time.monotonic() - began < 1.5


def test_a_value_said_of_a_point_is_no_vertical_line() -> None:
    """ "The gradient at x = 3" names a point: no line x = 3, as a line or a curve x = g(y)."""
    graph = _plot(
        "Find the gradient of y = x^2 at x = 3 and sketch the curve.",
        _curve("f", "x^2"),
        {"item": "curve", "name": "v", "x": "3"},
        {"item": "line", "name": "L", "x": "3"},
    )
    assert graph is not None and [c.label for c in graph.curves] == ["y = x²"] and not graph.lines


def test_a_derivative_the_question_gives_is_no_picture_of_f() -> None:
    """f'(x) = 3x² - 3 written as the curve y = 3x² - 3 would label f' as f."""
    graph = _plot("Given f'(x) = 3x^2 - 3 and f(0) = 1, sketch f.", _curve("f", "3x^2 - 3"))
    assert graph is None


def test_a_stated_interval_cut_where_the_curve_crosses_is_shaded() -> None:
    """u5-037: ∫ from -3 to 3 shaded in two parts cut at the crossing 0; π/2 written 1.5708."""
    odd = _plot(
        "Verify by computing ∫ from −3 to 3 of (x³ + x) dx, and show it.",
        _curve("f", "x^3 + x"),
        _shade("f", "x-axis", "-3", "0"),
        _shade("f", "x-axis", "0", "3"),
    )
    assert odd is not None and len(odd.regions) == 2
    sine = _plot(
        "Evaluate ∫ from −π/2 to π/2 of sin x dx. Show it on a graph.",
        _curve("f", "sin(x)"),
        _shade("f", "x-axis", "-1.5708", "1.5708"),
    )
    assert sine is not None and sine.regions


# Round 3 of the review (2026-11-15): each repro, held.


def _points_of(graph: PlotGraphSpec) -> set[tuple[float, float]]:
    return {(round(p.x, 3), round(p.y, 3)) for p in graph.points}


@pytest.mark.parametrize(
    ("question", "formula", "show"),
    [
        ("Sketch y = sin(5x) and mark where it crosses the x-axis.", "sin(5x)", "intercepts"),
        ("Sketch y = sin x and mark its turning points. (12 marks)", "sin(x)", "extrema"),
        (
            "A Ferris wheel's height is h(t) = 10 sin(t) + 12 metres after t seconds. Sketch h "
            "and find the height after 100 seconds.",
            "10 sin(t) + 12",
            "extrema",
        ),
    ],
)
def test_a_periodic_curve_is_drawn_around_the_origin(
    question: str, formula: str, show: str
) -> None:
    """A number said of nothing x is ("(12 marks)", "after 100 seconds") moves no window, and
    the places marked are the ones nearest the middle, every one in view."""
    graph = _plot(question, _curve("f", formula), {"item": "points", "of": "f", "show": [show]})
    assert graph is not None and graph.x_min < 0 < graph.x_max
    assert abs(graph.x_min + graph.x_max) < 0.25 * (graph.x_max - graph.x_min)
    assert all(graph.x_min <= p.x <= graph.x_max for p in graph.points)
    if "5x" in formula:
        assert (0.628, 0.0) in _points_of(graph)


@pytest.mark.parametrize(
    ("question", "formula", "domain"),
    [
        ("Sketch y = ln x for 0 ≤ x ≤ 3 and mark the ends.", "ln(x)", ["0", "3"]),
        ("Sketch y = 1/x on [0, 2] and mark its end points.", "1/x", ["0", "2"]),
        ("Sketch y = sqrt(x - 1) on [0, 5] and mark the ends.", "sqrt(x - 1)", ["0", "5"]),
    ],
)
def test_an_end_with_no_value_is_no_point_and_no_window(
    question: str, formula: str, domain: list[str]
) -> None:
    """NaN never reaches the fence (the phone refused the whole graph), and a pole at a
    stated end never sets the window (1/x on [0, 2] ran to y = 10⁷)."""
    body = json.dumps(
        {
            "kind": "plot",
            "items": [
                _curve("f", formula, domain=domain),
                {"item": "points", "of": "f", "show": ["ends"]},
            ],
        }
    )
    fence = drawn_fence(body, [question], "")
    assert fence is not None and "NaN" not in fence and "Infinity" not in fence
    graph = PlotGraphSpec.model_validate_json(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])
    assert graph.y_max - graph.y_min < 50 and graph.x_min <= 0.1


def test_a_region_beside_a_pole_at_a_stated_end_is_in_view() -> None:
    graph = _plot(
        "Find the area under y = 1/x from x = 1 to x = 3 and sketch y = 1/x for 0 < x ≤ 3.",
        _curve("f", "1/x", domain=["0", "3"]),
        _shade("f", "x-axis", "1", "3"),
    )
    assert graph is not None and graph.regions and graph.y_max < 50


@pytest.mark.parametrize(
    ("question", "description", "hole", "left"),
    [
        ("Sketch the graph of f(x) = (x^2 - 1)/(x - 1).", "x + 1", (1.0, 2.0), True),
        ("Sketch y = e^(ln x).", "x", None, False),
        ("Sketch y = (sqrt(x))^2.", "x", None, False),
        ("Sketch y = x/x and find where it is undefined.", "1", (0.0, 1.0), True),
    ],
)
def test_the_question_s_own_formula_keeps_its_holes_and_domain(
    question: str, description: str, hole: tuple[float, float] | None, left: bool
) -> None:
    """The reply's simplified formula draws as the question writes it."""
    graph = _plot(question, _curve("f", description))
    assert graph is not None
    xs = [x for curve in graph.curves for s in curve.segments for x, _y in s]
    assert (min(xs) < -0.5) == left
    if hole is not None:
        assert any(p.open and (round(p.x, 3), round(p.y, 3)) == hole for p in graph.points)


def test_a_domain_the_question_states_holds_without_the_description() -> None:
    graph = _plot(
        "The function f(x) = x^2 - 4x is defined for 0 ≤ x ≤ 3 only. Sketch f and mark its minimum.",
        _curve("f", "x^2 - 4x"),
        {"item": "points", "of": "f", "show": ["extrema", "intercepts"]},
    )
    assert graph is not None
    xs = [x for s in graph.curves[0].segments for x, _y in s]
    assert min(xs) >= -1e-9 and max(xs) <= 3 + 1e-9 and (4.0, 0.0) not in _points_of(graph)
    damped = _plot(
        "Sketch the damped oscillation y = e^(-x) cos(x) for x ≥ 0.", _curve("f", "e^(-x) cos(x)")
    )
    assert damped is not None and damped.y_max < 5 and damped.y_min > -5


def test_ends_a_domain_leaves_out_are_open() -> None:
    graph = _plot("Sketch f(x) = x^2 for 0 < x < 2.", _curve("f", "x^2", domain=["0", "2"]))
    assert graph is not None and graph.points and all(p.open for p in graph.points)


@pytest.mark.parametrize(
    "item",
    [
        _shade("f", "x-axis", "2", "3"),
        {"item": "rectangles", "under": "f", "from": "2", "to": "3", "n": 4, "rule": "left"},
    ],
)
def test_an_interval_said_of_an_answer_bounds_nothing(item: dict[str, Any]) -> None:
    graph = _plot(
        "Find the area under y = x^2 from x = 0 to x = 2 and check that your answer is "
        "between 2 and 3. Shade it.",
        _curve("f", "x^2"),
        item,
    )
    assert graph is None or not graph.regions


def test_a_rule_is_read_by_the_method_reader_not_its_words() -> None:
    """ "increasing to the right" names no right sum; "mid" in "pyramid" no midpoint."""
    rectangles = {
        "item": "rectangles",
        "under": "f",
        "from": "0",
        "to": "2",
        "n": 4,
        "rule": "right",
    }
    graph = _plot(
        "Estimate the area under f(x) = x^2 on [0, 2] using 4 rectangles with heights at the "
        "left endpoints. Is the result too high or too low? Explain whether the curve is "
        "increasing to the right.",
        _curve("f", "x^2"),
        rectangles,
    )
    assert graph is None or not graph.regions


@pytest.mark.parametrize(
    ("question", "description", "kept"),
    [
        (
            "A triangle has vertices (0, 0), (4, 0) and (0, 3). Find its area and draw it.",
            {"item": "line", "name": "L", "through": [["4", "0"], ["0", "3"]]},
            "Area = 6",
        ),
        (
            "A triangle has vertices (0, 0), (4, 0) and (0, 3). Find its area and draw it.",
            {"item": "line", "name": "L", "y": "-3x/4 + 3"},
            "Area = 6",
        ),
    ],
)
def test_a_line_the_server_works_out_is_named_only_as_the_reply_writes_it(
    question: str, description: dict[str, Any], kept: str
) -> None:
    graph = _plot(question, description, reply=kept)
    assert graph is not None and all(not c.label for c in graph.curves)
    named = _plot(question, description, reply="The hypotenuse is y = -3x/4 + 3.")
    assert named is not None and any(c.label for c in named.curves)


def test_a_tangent_stands_where_the_question_asks() -> None:
    """At x = 1, not at the end 2 of the interval it sketches on."""
    graph = _plot(
        "Find the tangent to y = x^3 at x = 1 and sketch the curve on [-2, 2].",
        _curve("f", "x^3"),
        {"item": "tangent", "to": "f", "at": "2"},
    )
    assert graph is not None and not graph.lines


def test_the_gradient_where_y_is_4_draws_no_line_y_4() -> None:
    graph = _plot(
        "Sketch y = x^2 and find the gradient where y = 4.",
        _curve("f", "x^2"),
        {"item": "line", "name": "L", "y": "4"},
    )
    assert graph is not None and not graph.lines


def test_a_curve_runs_to_the_end_of_its_domain_and_its_corner_is_a_turn() -> None:
    circle = _plot("Sketch y = sqrt(9 - x^2).", _curve("f", "sqrt(9 - x^2)"))
    assert circle is not None
    xs = [x for s in circle.curves[0].segments for x, _y in s]
    assert min(xs) == pytest.approx(-3, abs=1e-6) and max(xs) == pytest.approx(3, abs=1e-6)
    peak = _plot(
        "f(x) = x + 1 if x < 2, and f(x) = 5 - x if x >= 2. Sketch f and mark its maximum.",
        _curve("f", pieces=[{"y": "x + 1", "when": "x < 2"}, {"y": "5 - x", "when": "x >= 2"}]),
        {"item": "points", "of": "f", "show": ["extrema"]},
    )
    assert peak is not None and (2.0, 3.0) in _points_of(peak)


def test_tan_s_asymptotes_are_named_where_the_reply_names_them() -> None:
    graph = _plot(
        "Sketch y = tan x and its asymptotes.",
        _curve("f", "tan(x)"),
        {"item": "asymptotes", "of": "f"},
        reply="x = pi/2",
    )
    assert graph is not None
    assert any(line.label == "x = π/2" for line in graph.lines)
    poles = [line.start[0] for line in graph.lines if line.role == "asymptote"]
    assert all(graph.x_min <= x <= graph.x_max for x in poles)
    assert graph.x_max < 10.5


def test_an_antiderivative_as_the_card_writes_it_draws() -> None:
    graph = _plot(
        "Find the antiderivatives of f(x) = (x + 1)^2 and sketch the family.",
        _curve("F", "(x + 1)^3/3", shifts=["-1", "0", "1"]),
    )
    assert graph is not None and len(graph.curves) == 3
