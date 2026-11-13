"""The picture a maths question asks to see, drawn from the question's own values.

The textbook run (2026-11-13) got a parallelogram "8 units by 5" for angle A = 70°, a
triangle that was not right-angled for legs 9 and 12, and nothing at all for a rhombus,
a cube, a conversion graph, points in four quadrants or an interval. Each picture here is
built from a reading of the question as the read model gives it; each is held to the
values the question states, and a reading that invents or miscopies one draws nothing.
"""

from __future__ import annotations

import json
import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.math.figure.build import figure_fence
from app.modules.math.figure.drawing import angle_at, distance
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec, PointsGraphSpec


def _draw(question: str, reading: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    fence = figure_fence(FigureRequest.model_validate(reading), [question])
    if fence is None:
        return None
    lang, _, rest = fence.removeprefix("```").partition("\n")
    return lang, json.loads(rest.rsplit("\n```", 1)[0])


def _figure(question: str, reading: dict[str, Any]) -> FigureSpec:
    drawn = _draw(question, reading)
    assert drawn is not None and drawn[0] == "geometry"
    return FigureSpec.model_validate(drawn[1])


def _labels(spec: FigureSpec) -> set[str]:
    return {s.label for s in spec.segments if s.label} | {a.label for a in spec.angles if a.label}


def _at(spec: FigureSpec, name: str) -> tuple[float, float]:
    point = next(p for p in spec.points if p.name == name)
    return (point.x, point.y)


def _length(spec: FigureSpec, a: str, b: str) -> float:
    return distance(_at(spec, a), _at(spec, b))


def _angle(spec: FigureSpec, at: str, a: str, b: str) -> float:
    return angle_at(_at(spec, at), _at(spec, a), _at(spec, b))


PARALLELOGRAM = (
    "In parallelogram ABCD, angle A = 70°. Find angles B, C and D, and draw the parallelogram."
)
RIGHT_TRIANGLE = (
    "A right-angled triangle has legs of 9 cm and 12 cm. Find its hypotenuse and draw the triangle."
)


def test_a_parallelogram_carries_its_stated_angle_and_no_invented_side() -> None:
    reading = {
        "kind": "polygon",
        "shape": "parallelogram",
        "vertices": "ABCD",
        "measures": [{"what": "angle", "name": "A", "value": 70}],
    }
    spec = _figure(PARALLELOGRAM, reading)
    assert _labels(spec) == {"70°"}
    assert _angle(spec, "A", "B", "D") == pytest.approx(70, abs=1e-6)
    assert _angle(spec, "B", "A", "C") == pytest.approx(110, abs=1e-6)
    assert _length(spec, "A", "B") == pytest.approx(_length(spec, "D", "C"))
    assert {p.name for p in spec.points if p.show} == {"A", "B", "C", "D"}


def test_a_right_triangle_is_right_angled_with_the_stated_legs() -> None:
    reading = {
        "kind": "polygon",
        "shape": "right_triangle",
        "measures": [{"what": "leg", "value": 9}, {"what": "leg", "value": 12}],
        "unit": "cm",
    }
    spec = _figure(RIGHT_TRIANGLE, reading)
    assert _labels(spec) == {"9 cm", "12 cm"}
    assert any(angle.right for angle in spec.angles)
    legs = sorted(s for s in (_length(spec, "A", "B"), _length(spec, "A", "C")))
    assert legs == pytest.approx([9, 12])
    assert _length(spec, "B", "C") == pytest.approx(15)


@pytest.mark.parametrize(
    "question, reading, labels, check",
    [
        (
            "In triangle ABC, angle A = 50° and angle B = 65°. Find angle C and draw it.",
            {
                "kind": "polygon",
                "shape": "triangle",
                "vertices": "ABC",
                "measures": [
                    {"what": "angle", "name": "A", "value": 50},
                    {"what": "angle", "name": "B", "value": 65},
                ],
            },
            {"50°", "65°"},
            lambda s: _angle(s, "C", "A", "B") == pytest.approx(65, abs=1e-6),
        ),
        (
            "The perimeter of an isosceles triangle ABC is 14 cm and its base is 6 cm. Draw it.",
            {
                "kind": "polygon",
                "shape": "isosceles_triangle",
                "vertices": "ABC",
                "measures": [{"what": "perimeter", "value": 14}, {"what": "base", "value": 6}],
                "unit": "cm",
            },
            {"6 cm"},
            lambda s: sorted([_length(s, "A", "C"), _length(s, "B", "C")]) == pytest.approx([4, 4]),
        ),
        (
            "Draw a triangle with sides 5 cm, 6 cm and 7 cm.",
            {
                "kind": "polygon",
                "shape": "triangle",
                "measures": [
                    {"what": "side", "value": 5},
                    {"what": "side", "value": 6},
                    {"what": "side", "value": 7},
                ],
                "unit": "cm",
            },
            {"5 cm", "6 cm", "7 cm"},
            lambda s: (
                sorted(_length(s, a, b) for a, b in (("A", "B"), ("B", "C"), ("A", "C")))
                == pytest.approx([5, 6, 7])
            ),
        ),
        (
            "Draw an equilateral triangle of side 4 cm.",
            {
                "kind": "polygon",
                "shape": "equilateral_triangle",
                "measures": [{"what": "side", "value": 4}],
                "unit": "cm",
            },
            {"4 cm"},
            lambda s: (
                all(seg.ticks == 1 for seg in s.segments)
                and _angle(s, "A", "B", "C") == pytest.approx(60, abs=1e-6)
            ),
        ),
        (
            "Draw a triangle with base 8 cm and height 5 cm.",
            {
                "kind": "polygon",
                "shape": "triangle",
                "measures": [{"what": "base", "value": 8}, {"what": "height", "value": 5}],
                "unit": "cm",
            },
            {"8 cm", "5 cm"},
            lambda s: any(seg.dashed for seg in s.segments),
        ),
    ],
)
def test_triangles_take_the_question_s_values(question, reading, labels, check) -> None:
    spec = _figure(question, reading)
    assert _labels(spec) == labels
    assert check(spec)


@pytest.mark.parametrize(
    "question, reading, labels, check",
    [
        (
            "The diagonals of a rhombus are 10 cm and 24 cm. Find its side and draw the rhombus.",
            {
                "kind": "polygon",
                "shape": "rhombus",
                "measures": [{"what": "diagonal", "value": 10}, {"what": "diagonal", "value": 24}],
                "unit": "cm",
            },
            {"10 cm", "24 cm"},
            lambda s: _length(s, "A", "B") == pytest.approx(13),
        ),
        (
            "A trapezium has parallel sides 9 cm and 15 cm and a height of 6 cm. Draw it.",
            {
                "kind": "polygon",
                "shape": "trapezium",
                "measures": [
                    {"what": "parallel_side", "value": 9},
                    {"what": "parallel_side", "value": 15},
                    {"what": "height", "value": 6},
                ],
                "unit": "cm",
            },
            {"9 cm", "15 cm", "6 cm"},
            lambda s: (
                _length(s, "A", "B") == pytest.approx(15)
                and _length(s, "D", "C") == pytest.approx(9)
            ),
        ),
        (
            "Draw a square ABCD of side 5 cm and its diagonals meeting at O.",
            {
                "kind": "polygon",
                "shape": "square",
                "vertices": "ABCD",
                "center": "O",
                "measures": [{"what": "side", "value": 5}],
                "parts": ["diagonals"],
                "unit": "cm",
            },
            {"5 cm"},
            lambda s: _at(s, "O") == pytest.approx((2.5, 2.5)),
        ),
        (
            "Draw a rectangle 8 cm long and 3 cm wide.",
            {
                "kind": "polygon",
                "shape": "rectangle",
                "measures": [{"what": "length", "value": 8}, {"what": "width", "value": 3}],
                "unit": "cm",
            },
            {"8 cm", "3 cm"},
            lambda s: sum(a.right for a in s.angles) == 4,
        ),
        (
            "Draw a kite whose diagonals are 6 cm and 10 cm.",
            {
                "kind": "polygon",
                "shape": "kite",
                "measures": [{"what": "diagonal", "value": 6}, {"what": "diagonal", "value": 10}],
                "unit": "cm",
            },
            {"6 cm", "10 cm"},
            lambda s: _length(s, "A", "C") == pytest.approx(10),
        ),
        (
            "Find each interior angle of a regular hexagon, and draw the hexagon.",
            {"kind": "polygon", "shape": "regular_polygon", "sides": 6},
            set(),
            lambda s: (
                s.shape == "regular_polygon_6"
                and _angle(s, "B", "A", "C") == pytest.approx(120, abs=1e-6)
            ),
        ),
        (
            "Draw a regular pentagon with sides of 3 cm.",
            {
                "kind": "polygon",
                "shape": "regular_polygon",
                "sides": 5,
                "measures": [{"what": "side", "value": 3}],
                "unit": "cm",
            },
            {"3 cm"},
            lambda s: len(s.points) == 5,
        ),
    ],
)
def test_quadrilaterals_and_regular_polygons(question, reading, labels, check) -> None:
    spec = _figure(question, reading)
    assert _labels(spec) == labels
    assert check(spec)


def test_a_chord_sits_at_its_true_distance_from_the_centre() -> None:
    question = "Draw a circle of radius 4 cm with a chord of length 6 cm. How far is the chord from the centre?"
    reading = {
        "kind": "circle", "shape": "circle", "unit": "cm",
        "measures": [{"what": "radius", "value": 4}, {"what": "chord", "value": 6}],
    }  # fmt: skip
    spec = _figure(question, reading)
    assert _labels(spec) == {"4 cm", "6 cm"}
    chord = next(s for s in spec.segments if s.label == "6 cm")
    assert _length(spec, chord.a, chord.b) == pytest.approx(6)
    assert abs(_at(spec, chord.a)[1]) == pytest.approx(math.sqrt(7))
    assert any(a.right for a in spec.angles)


def test_a_square_inside_a_circle_has_its_corners_on_it() -> None:
    question = "A square is cut out of a circle of radius 6 cm so that the corners of the square lie on the circle."
    reading = {
        "kind": "circle", "shape": "circle", "inscribed": "square", "unit": "cm",
        "measures": [{"what": "radius", "value": 6}],
    }  # fmt: skip
    spec = _figure(question, reading)
    corners = [p for p in spec.points if p.name in spec.faces[0]]
    assert len(corners) == 4
    assert all(math.hypot(p.x, p.y) == pytest.approx(6) for p in corners)
    assert _labels(spec) == {"6 cm"}


@pytest.mark.parametrize(
    "question, reading, label",
    [
        ("Two parallel lines are cut by a transversal. One of the angles formed is 65°. Draw it.",
         {"kind": "lines", "shape": "parallel_lines", "measures": [{"what": "angle", "value": 65}]},
         "65°"),
        ("Two lines cross at an angle of 40°. Draw them.",
         {"kind": "lines", "shape": "intersecting_lines", "measures": [{"what": "angle", "value": 40}]},
         "40°"),
        ("Draw angle ABC = 35°.",
         {"kind": "lines", "shape": "angle", "vertices": "ABC",
          "measures": [{"what": "angle", "name": "ABC", "value": 35}]},
         "35°"),
        ("An angle of 128° sits on a straight line. Draw it with its supplement.",
         {"kind": "lines", "shape": "angles_on_line", "measures": [{"what": "angle", "value": 128}]},
         "128°"),
    ],
)  # fmt: skip
def test_lines_and_angles_mark_the_stated_angle(question, reading, label) -> None:
    spec = _figure(question, reading)
    marked = next(a for a in spec.angles if a.label == label)
    assert _angle(spec, marked.at, marked.a, marked.b) == pytest.approx(float(label[:-1]), abs=1e-6)


def test_parallel_lines_are_parallel_and_marked() -> None:
    reading = {
        "kind": "lines",
        "shape": "parallel_lines",
        "measures": [{"what": "angle", "value": 65}],
    }
    spec = _figure("Two parallel lines are cut by a transversal at 65°.", reading)
    marked = [s for s in spec.segments if s.arrows]
    assert len(marked) == 2
    ys = {round(_at(spec, s.a)[1], 9) for s in marked}
    assert all(_at(spec, s.a)[1] == pytest.approx(_at(spec, s.b)[1]) for s in marked)
    assert len(ys) == 2


@pytest.mark.parametrize(
    "question, reading, labels, dashed",
    [
        ("Find the volume of a cube with sides of 4 m, and draw the cube.",
         {"kind": "solid", "shape": "cube", "measures": [{"what": "edge", "value": 4}], "unit": "m"},
         {"4 m"}, 3),
        ("A rectangular box is 8 cm long, 3 cm wide and 7 cm high. Draw the box.",
         {"kind": "solid", "shape": "cuboid", "unit": "cm",
          "measures": [{"what": "length", "value": 8}, {"what": "width", "value": 3},
                       {"what": "height", "value": 7}]},
         {"8 cm", "3 cm", "7 cm"}, 3),
        ("A right triangular prism has an altitude of 15 cm and a base with sides 6 cm, 8 cm and 10 cm.",
         {"kind": "solid", "shape": "triangular_prism", "unit": "cm",
          "measures": [{"what": "length", "value": 15}, {"what": "side", "value": 6},
                       {"what": "side", "value": 8}, {"what": "side", "value": 10}]},
         {"6 cm", "8 cm", "10 cm", "15 cm"}, 3),
        ("A cylinder has radius 3 cm and height 10 cm. Draw it.",
         {"kind": "solid", "shape": "cylinder", "unit": "cm",
          "measures": [{"what": "radius", "value": 3}, {"what": "height", "value": 10}]},
         {"3 cm", "10 cm"}, 0),
        ("Draw a cone of radius 3 cm and height 4 cm.",
         {"kind": "solid", "shape": "cone", "unit": "cm",
          "measures": [{"what": "radius", "value": 3}, {"what": "height", "value": 4}]},
         {"3 cm", "4 cm"}, 2),
        ("Draw a square pyramid with base 6 cm and height 4 cm.",
         {"kind": "solid", "shape": "square_pyramid", "unit": "cm",
          "measures": [{"what": "base", "value": 6}, {"what": "height", "value": 4}]},
         {"6 cm", "4 cm"}, 4),
        ("Draw a sphere of radius 5 cm.",
         {"kind": "solid", "shape": "sphere", "unit": "cm",
          "measures": [{"what": "radius", "value": 5}]},
         {"5 cm"}, 0),
    ],
)  # fmt: skip
def test_solids_label_their_stated_sizes_and_dash_hidden_edges(
    question, reading, labels, dashed
) -> None:
    spec = _figure(question, reading)
    assert _labels(spec) == labels
    assert sum(seg.dashed for seg in spec.segments) == dashed


@pytest.mark.parametrize(
    "shape, measures, edges",
    [
        ("cube", [{"what": "edge", "value": 3}], 19),
        ("cuboid", [{"what": "length", "value": 4}, {"what": "width", "value": 2},
                    {"what": "height", "value": 3}], 19),
        ("triangular_prism", [{"what": "side", "value": 3}, {"what": "side", "value": 4},
                              {"what": "side", "value": 5}, {"what": "length", "value": 6}], 14),
        ("square_pyramid", [{"what": "base", "value": 4}, {"what": "height", "value": 3}], 12),
    ],
)  # fmt: skip
def test_nets_unfold_every_face(shape, measures, edges) -> None:
    values = ", ".join(str(m["value"]) for m in measures)
    reading = {
        "kind": "solid",
        "shape": shape,
        "measures": measures,
        "parts": ["net"],
        "unit": "cm",
    }
    spec = _figure(f"Draw the net of a {shape} with sides {values} cm.", reading)
    assert spec.shape == f"{shape}_net"
    # Each fold drawn once: a cube's cross of six squares has 19 edges.
    assert len([s for s in spec.segments if not s.dashed]) == edges


def test_a_number_line_marks_the_numbers_as_written() -> None:
    question = "Represent the rational numbers -5/2, -1/3, 3/4 and 1.5 on a number line."
    reading = {"kind": "number_line", "numbers": ["-5/2", "-1/3", "3/4", "1.5"]}
    drawn = _draw(question, reading)
    assert drawn is not None and drawn[0] == "graph"
    graph = drawn[1]
    assert graph["type"] == "number_line"
    assert [m["label"] for m in graph["marks"]] == ["−5/2", "−1/3", "3/4", "1.5"]
    assert [m["x"] for m in graph["marks"]] == pytest.approx([-2.5, -1 / 3, 0.75, 1.5])
    assert all(i["start"] == i["end"] and i["start_inclusive"] for i in graph["intervals"])


@pytest.mark.parametrize(
    "question, inequality, interval",
    [
        ("Show -2 < x ≤ 3 on a number line.", "-2 < x ≤ 3", (-2.0, 3.0, False, True)),
        ("Show x ≥ 4 on a number line.", "x ≥ 4", (4.0, None, True, False)),
        ("Draw 1 < x < 5 on a number line.", "1 < x < 5", (1.0, 5.0, False, False)),
    ],
)
def test_a_number_line_shades_the_inequality_the_question_writes(
    question: str, inequality: str, interval: tuple[Any, ...]
) -> None:
    drawn = _draw(question, {"kind": "number_line", "inequality": inequality})
    assert drawn is not None
    shown = drawn[1]["intervals"][0]
    got = (shown["start"], shown["end"], shown["start_inclusive"], shown["end_inclusive"])
    assert got == interval


def test_a_miscopied_inequality_draws_nothing() -> None:
    # The question's ≤ read as <: the open circle would be wrong.
    question = "Show -2 < x ≤ 3 on a number line."
    assert _draw(question, {"kind": "number_line", "inequality": "-2 < x < 3"}) is None


@pytest.mark.parametrize(
    "question, reading, explicit, ys",
    [
        ("Draw the graph of y = -x + 4 and find where it crosses the axes.",
         {"kind": "function", "expr": "-x + 4"},
         False, (14.0, -6.0)),
        ("Draw the graph of y = 2x + 1 for x from -3 to 3.",
         {"kind": "function", "expr": "2x + 1", "x_min": -3, "x_max": 3},
         True, (-5.0, 7.0)),
    ],
)  # fmt: skip
def test_function_graphs_cover_the_stated_range(question, reading, explicit, ys) -> None:
    drawn = _draw(question, reading)
    assert drawn is not None and drawn[0] == "graph"
    graph = drawn[1]
    assert graph["type"] == "function" and graph["domain_explicit"] is explicit
    assert (graph["points"][0][1], graph["points"][-1][1]) == pytest.approx(ys)


def test_a_function_the_question_writes_is_drawn_only_as_written() -> None:
    # "2x - 1" for the question's y = 2x + 1: SymPy compares them, and nothing is drawn.
    question = "Draw the graph of y = 2x + 1 for x from -3 to 3."
    assert _draw(question, {"kind": "function", "expr": "2x - 1", "x_min": -3, "x_max": 3}) is None


def test_points_are_plotted_in_their_quadrants() -> None:
    question = (
        "Plot the points A(2, 3), B(-1, 4), C(-3, -2) and D(4, -1) and name the quadrant of each."
    )
    reading = {
        "kind": "points", "quadrants": True,
        "points": [{"name": "A", "x": 2, "y": 3}, {"name": "B", "x": -1, "y": 4},
                   {"name": "C", "x": -3, "y": -2}, {"name": "D", "x": 4, "y": -1}],
    }  # fmt: skip
    drawn = _draw(question, reading)
    assert drawn is not None and drawn[0] == "graph"
    graph = PointsGraphSpec.model_validate(drawn[1])
    assert [p.label for p in graph.points] == ["A(2, 3)", "B(−1, 4)", "C(−3, −2)", "D(4, −1)"]
    assert graph.quadrants and graph.x_min <= -3 and graph.y_max >= 4


@pytest.mark.parametrize(
    "question, reading",
    [
        # A leg the question never gave (8 for 9).
        (RIGHT_TRIANGLE, {"kind": "polygon", "shape": "right_triangle",
                          "measures": [{"what": "leg", "value": 8}, {"what": "leg", "value": 12}]}),
        # A default size filled in for the parallelogram.
        (PARALLELOGRAM, {"kind": "polygon", "shape": "parallelogram", "vertices": "ABCD",
                         "measures": [{"what": "angle", "name": "A", "value": 70},
                                      {"what": "base", "value": 8}]}),
        # Sides no triangle has.
        ("Draw a triangle with sides 2, 3 and 9.",
         {"kind": "polygon", "shape": "triangle", "measures": [
             {"what": "side", "value": 2}, {"what": "side", "value": 3}, {"what": "side", "value": 9}]}),
        # Angles past 180°.
        ("In triangle ABC, angle A = 100° and angle B = 95°.",
         {"kind": "polygon", "shape": "triangle", "vertices": "ABC", "measures": [
             {"what": "angle", "name": "A", "value": 100}, {"what": "angle", "name": "B", "value": 95}]}),
        # A chord longer than the diameter.
        ("A circle of radius 2 cm has a chord of 9 cm.",
         {"kind": "circle", "shape": "circle", "measures": [
             {"what": "radius", "value": 2}, {"what": "chord", "value": 9}]}),
        # A point the question never named.
        ("Plot A(2, 3) on a coordinate plane.",
         {"kind": "points", "points": [{"name": "A", "x": 2, "y": 5}]}),
        # Data to chart is the reply's own chart.
        ("Draw a bar graph: Grade 5: 40, Grade 6: 55.", {"kind": "none"}),
        # A shape the builders do not know.
        ("Draw a dodecahedron.", {"kind": "solid", "shape": "dodecahedron"}),
    ],
)  # fmt: skip
def test_a_reading_that_does_not_hold_draws_nothing(question: str, reading: dict[str, Any]) -> None:
    assert _draw(question, reading) is None


@pytest.mark.parametrize(
    "question, reading",
    [
        ("Draw a parallelogram.", {"kind": "polygon", "shape": "parallelogram"}),
        ("Draw a triangle.", {"kind": "polygon", "shape": "triangle"}),
        ("Draw a cube.", {"kind": "solid", "shape": "cube"}),
        ("Draw a circle.", {"kind": "circle", "shape": "circle"}),
    ],
)
def test_a_shape_with_no_stated_size_is_drawn_unlabelled(
    question: str, reading: dict[str, Any]
) -> None:
    assert _labels(_figure(question, reading)) == set()


def test_a_number_in_words_or_a_polygon_name_counts_as_stated() -> None:
    reading = {"kind": "polygon", "shape": "regular_polygon", "sides": 8,
               "measures": [{"what": "side", "value": 2}], "unit": "cm"}  # fmt: skip
    assert _draw("Draw a regular octagon with sides of two centimetres.", reading) is not None


def test_a_kite_is_lettered_where_its_named_sides_put_the_letters() -> None:
    question = "Draw a kite ABCD with AB = AD = 5 cm and CB = CD = 8 cm."
    reading = {
        "kind": "polygon", "shape": "kite", "vertices": "ABCD", "unit": "cm",
        "measures": [{"what": "equal_side", "name": "AB", "value": 5},
                     {"what": "equal_side", "name": "AD", "value": 5},
                     {"what": "equal_side", "name": "CB", "value": 8},
                     {"what": "equal_side", "name": "CD", "value": 8}],
    }  # fmt: skip
    spec = _figure(question, reading)
    assert _length(spec, "A", "B") == pytest.approx(5)
    assert _length(spec, "A", "D") == pytest.approx(5)
    assert _length(spec, "C", "B") == pytest.approx(8)


def test_named_values_no_lettering_meets_draw_nothing() -> None:
    # A rectangle "ABCD" with AB = 8 and AC = 3: a diagonal shorter than a side.
    question = "Draw rectangle ABCD with AB = 8 cm and AC = 3 cm."
    reading = {
        "kind": "polygon", "shape": "rectangle", "vertices": "ABCD", "unit": "cm",
        "measures": [{"what": "side", "name": "AB", "value": 8},
                     {"what": "diagonal", "name": "AC", "value": 3}],
    }  # fmt: skip
    assert _draw(question, reading) is None


def test_a_lettered_centre_stays_where_the_diagonals_meet() -> None:
    question = "Square ABCD has side AB = 5 cm; its diagonals meet at O. Draw it."
    reading = {
        "kind": "polygon", "shape": "square", "vertices": "ABCD", "center": "O", "unit": "cm",
        "parts": ["diagonals"], "measures": [{"what": "side", "name": "AB", "value": 5}],
    }  # fmt: skip
    spec = _figure(question, reading)
    assert _at(spec, "O") == pytest.approx((2.5, 2.5))
    assert _length(spec, "A", "B") == pytest.approx(5)


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", [AsyncMock(return_value=True), AsyncMock(side_effect=OSError)])
async def test_no_read_past_the_spend_cap_or_in_an_outage(gate: AsyncMock) -> None:
    """The read is a hint: past the spend cap, or with the spend read down, there is no
    picture and the reply stands."""
    from app.core.config import Settings
    from app.modules.math.figure import read

    with (
        patch("app.core.redis.get_redis_client", MagicMock()),
        patch("app.services.quota.global_spend_exceeded", gate),
        patch("app.gateways.structured_completion.complete_structured", AsyncMock()) as call,
    ):
        assert await read.read_figure(Settings(_env_file=None), PARALLELOGRAM, []) is None  # type: ignore[call-arg]
    call.assert_not_awaited()
