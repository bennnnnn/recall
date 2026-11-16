"""The owner's drawing decisions of 2026-11-16 (feat/draw-more): a legend row names only
the lines it labels; a vector in the plane described as (a, b, 0) is drawn flat."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.math.drawing.build import drawn_fence
from app.modules.math.drawing.plot_scene import NEUTRAL_COLOR
from app.tests.modules.math.drawing.test_plot_review import _curve, _plot


def _tangent(to: str, at: str) -> dict[str, str]:
    return {"item": "tangent", "to": to, "at": at}


def test_each_tangent_takes_its_curve_s_colour() -> None:
    # u5-006: three tangents in one colour beside one legend row, y = 2x.
    graph = _plot(
        "Draw y = x² − 1, y = x² and y = x² + 1 on the same axes and show that at x = 1 they "
        "all have the same slope.",
        _curve("f", "x^2 - 1"),
        _curve("g", "x^2"),
        _curve("h", "x^2 + 1"),
        _tangent("f", "1"),
        _tangent("g", "1"),
        _tangent("h", "1"),
        reply="The tangent to y = x² + 1 at x = 1 is y = 2x.",
    )
    assert graph is not None
    curves = [curve.color for curve in graph.curves]
    assert [line.color for line in graph.lines] == curves
    assert [line.label for line in graph.lines] == ["", "", "y = 2x"]


def test_asymptotes_take_their_curve_s_colour() -> None:
    graph = _plot(
        "Sketch y = 1/(x − 2) and y = x² and show the asymptotes.",
        _curve("g", "x^2"),
        _curve("f", "1/(x - 2)"),
        {"item": "asymptotes", "of": "f"},
        reply="The asymptotes are x = 2 and y = 0.",
    )
    assert graph is not None
    own = next(curve.color for curve in graph.curves if curve.label == "y = 1/(x − 2)")
    asymptotes = [line for line in graph.lines if line.role == "asymptote"]
    assert asymptotes and {line.color for line in asymptotes} == {own}
    assert {line.label for line in asymptotes} == {"x = 2", "y = 0"}


_D06 = "Draw the vectors u = (2, 1) and v = (1, 3) and find the angle between them."


def _space(question: str, *items: dict[str, Any], reply: str = "") -> dict[str, Any] | None:
    body = json.dumps({"kind": "space", "items": [{"item": "axes"}, *items]})
    fence = drawn_fence(body, [question], reply)
    return None if fence is None else json.loads(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])


def _vector(name: str, to: list[int], **more: Any) -> dict[str, Any]:
    return {"item": "vector", "name": name, "to": to, **more}


def _at(figure: dict[str, Any], label: str) -> tuple[float, float]:
    segment = next(s for s in figure["segments"] if s.get("label") == label)
    tip = next(p for p in figure["points"] if p["name"] == segment["b"])
    return tip["x"], tip["y"]


def test_vectors_in_the_plane_are_drawn_flat() -> None:
    figure = _space(
        _D06,
        _vector("u", [2, 1, 0]),
        _vector("v", [1, 3, 0]),
        {"item": "angle", "at": "O", "between": ["u", "v"], "label": "θ"},
        reply="cos θ = 5/(√5·√10), so θ = 45°.",
    )
    assert figure is not None
    # Seen from above: each tip at its own pair, x across and y up; no z-axis.
    assert _at(figure, "u") == pytest.approx((2, 1))
    assert _at(figure, "v") == pytest.approx((1, 3))
    names = {p["name"] for p in figure["points"] if p.get("show")}
    assert {"x", "y"} <= names and "z" not in names
    assert figure["angles"][0]["label"] == "θ = 45°"


@pytest.mark.parametrize(
    ("question", "to"),
    [
        (_D06, [2, 1, 1]),  # (2, 1, 1) is no vector it writes
        (_D06, [2, 2, 0]),  # nor is (2, 2)
        ("Draw the vectors u = (2, 1, 0) and v = (0, 1, 3).", [2, 1, 3]),
    ],
)
def test_a_vector_it_does_not_write_is_not_drawn(question: str, to: list[int]) -> None:
    assert _space(question, _vector("u", to)) is None


def test_a_vector_in_space_is_still_seen_in_space() -> None:
    figure = _space("Draw the vector a = (2, 1, 3).", _vector("a", [2, 1, 3]))
    assert figure is not None
    assert "z" in {p["name"] for p in figure["points"] if p.get("show")}


def test_a_plane_vector_from_another_point_only_as_written_as_a_vector() -> None:
    question = "Let A(1, 1) and u = (2, 1). Draw u from A."
    drawn = _space(question, {"item": "point", "name": "A", "at": [1, 1, 0]},
                   _vector("u", [2, 1, 0], **{"from": "A"}))  # fmt: skip
    assert drawn is not None and _at(drawn, "u") == pytest.approx((3, 2))
    point = "Let A(1, 1) and B(2, 1). Draw an arrow from A."
    other = _space(point, {"item": "point", "name": "A", "at": [1, 1, 0]},
                   _vector("w", [2, 1, 0], **{"from": "A"}))  # fmt: skip
    assert other is None or not any(s.get("label") == "w" for s in other["segments"])


@pytest.mark.parametrize(
    "question",
    [
        "On the face z = 0 of a cube, draw the vectors u = (2, 1) and v = (1, 3) in 3D.",
        "Draw the vectors u = (2, 1) and v = (1, 3) in space.",
        "A box stands on the floor; draw u = (2, 1) and v = (1, 3) on its base.",
    ],
)
def test_a_question_that_names_space_or_a_solid_is_seen_in_space(question: str) -> None:
    figure = _space(question, _vector("u", [2, 1, 0]), _vector("v", [1, 3, 0]))
    # The pairs are no triples it writes: in space, nothing it states is drawn.
    assert figure is None or "z" in {p["name"] for p in figure["points"] if p.get("show")}


def test_normals_and_level_lines_take_a_colour_no_curve_or_line_uses() -> None:
    graph = _plot(
        "Sketch y = x^2, y = x^3 and y = x^4, and the tangent and normal to y = x^4 at x = 1.",
        _curve("f", "x^2"),
        _curve("g", "x^3"),
        _curve("h", "x^4"),
        _tangent("h", "1"),
        {"item": "normal", "to": "h", "at": "1"},
    )
    assert graph is not None
    assert [c.color for c in graph.curves] == [0, 1, 2]
    assert [line.color for line in graph.lines] == [2, 3]  # the tangent is x⁴'s; the normal free
    average = _plot(
        "Find the average value of f(x) = x^2 on [0, 3] and the normal at x = 1. Sketch.",
        _curve("f", "x^2"),
        {"item": "average", "of": "f", "from": "0", "to": "3"},
        {"item": "normal", "to": "f", "at": "1"},
    )
    assert average is not None and len({line.color for line in average.lines}) == 2
    assert 0 not in {line.color for line in average.lines}


def test_a_line_two_curves_share_is_drawn_once_and_neutral() -> None:
    graph = _plot(
        "Sketch y = 1/x and y = 1/(x - 1) with their asymptotes.",
        _curve("f", "1/x"),
        _curve("g", "1/(x - 1)"),
        {"item": "asymptotes", "of": "f"},
        {"item": "asymptotes", "of": "g"},
    )
    assert graph is not None
    level = [line for line in graph.lines if line.start[1] == line.end[1] == 0]
    assert len(level) == 1 and level[0].color == NEUTRAL_COLOR
