"""A picture is drawn only when it honours every value and property the question states.

The review of the server's pictures (2026-11-13) found pictures that kept the numbers but
not the question: the right angle on a 67° corner of a 13-5-12 triangle, an isosceles
triangle's 40° apex drawn as a base angle, every inscribed triangle equilateral, a cone's
diameter written on its radius, a prism's end invented, a diagonal's angle drawn at a
corner, 40° written in a right-angle box, the 3 of "x = 3" drawn as y = 3, and readings
that kept a number while changing its sign, unit or role. Each case here is either drawn
true to the question or not drawn at all.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.math.figure.build import figure_fence
from app.modules.math.figure.drawing import angle_at, distance
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec


def _draw(question: str, reading: dict[str, Any], *earlier: str) -> tuple[str, Any] | None:
    fence = figure_fence(FigureRequest.model_validate(reading), [question, *earlier])
    if fence is None:
        return None
    lang, _, rest = fence.removeprefix("```").partition("\n")
    return lang, json.loads(rest.rsplit("\n```", 1)[0])


def _figure(question: str, reading: dict[str, Any]) -> FigureSpec:
    drawn = _draw(question, reading)
    assert drawn is not None and drawn[0] == "geometry"
    return FigureSpec.model_validate(drawn[1])


def _at(spec: FigureSpec, name: str) -> tuple[float, float]:
    point = next(p for p in spec.points if p.name == name)
    return (point.x, point.y)


def _side(spec: FigureSpec, a: str, b: str) -> tuple[float, str | None, int]:
    segment = next(s for s in spec.segments if {s.a, s.b} == {a, b})
    return distance(_at(spec, a), _at(spec, b)), segment.label, segment.ticks


def _right_at(spec: FigureSpec) -> list[str]:
    return [mark.at for mark in spec.angles if mark.right]


def _tri(shape: str, measures: list[dict[str, Any]], vertices: str = "", **extra: Any) -> dict:
    return {"kind": "polygon", "shape": shape, "vertices": vertices, "measures": measures}


def _cm(reading: dict[str, Any]) -> dict[str, Any]:
    return {**reading, "unit": "cm"}


def _s(value: float, name: str = "", what: str = "side") -> dict[str, Any]:
    return {"what": what, "name": name, "value": value}


@pytest.mark.parametrize(
    "question, measures, vertices, right, hypotenuse",
    [
        ("A right triangle has sides 13 cm, 5 cm and 12 cm. Draw it.",
         [_s(13), _s(5), _s(12)], "", None, 13.0),
        ("Draw a right-angled triangle with sides 10 cm, 6 cm and 8 cm.",
         [_s(10), _s(6), _s(8)], "", None, 10.0),
        ("Right triangle ABC has AB = 13 cm, BC = 5 cm and CA = 12 cm. Draw it.",
         [_s(13, "AB"), _s(5, "BC"), _s(12, "CA")], "ABC", "C", 13.0),
        ("Triangle PQR is right-angled at Q, PQ = 6 cm, PR = 10 cm. Draw it.",
         [{"what": "angle", "name": "Q", "value": 90}, _s(6, "PQ"), _s(10, "PR")], "PQR", "Q",
         10.0),
        ("Triangle ABC has a right angle at B, AB = 3 cm and AC = 5 cm. Draw it.",
         [_s(3, "AB", "leg"), _s(5, "AC", "hypotenuse")], "ABC", "B", 5.0),
    ],
)  # fmt: skip
def test_a_right_angle_sits_where_the_question_puts_it(
    question: str, measures: list[dict[str, Any]], vertices: str, right: str | None,
    hypotenuse: float,
) -> None:  # fmt: skip
    spec = _figure(question, _cm(_tri("right_triangle", measures, vertices)))
    (corner,) = _right_at(spec)
    if right is not None:
        assert corner == right
    others = [p.name for p in spec.points if p.name in spec.faces[0] and p.name != corner]
    assert _side(spec, *others)[0] == pytest.approx(hypotenuse)
    assert angle_at(_at(spec, corner), *(_at(spec, n) for n in others)) == pytest.approx(90)


@pytest.mark.parametrize(
    "question, reading",
    [
        ("A right triangle has legs 5 cm and hypotenuse 4 cm. Draw it.",
         _tri("right_triangle", [_s(5, what="leg"), _s(4, what="hypotenuse")])),
        ("Draw a right triangle with sides 4 cm, 5 cm and 6 cm.",
         _tri("right_triangle", [_s(4), _s(5), _s(6)])),
        # Legs or a leg and the hypotenuse: the question does not say.
        ("A right triangle has sides 5 cm and 13 cm. Draw it.",
         _tri("right_triangle", [_s(5), _s(13)])),
        # The apex is not read, so 40° could be either kind of angle.
        ("Triangle ABC is isosceles with AB = AC and angle A = 40°. Draw it.",
         _tri("isosceles_triangle", [{"what": "angle", "name": "A", "value": 40}], "ABC")),
        ("An isosceles triangle has an angle of 40°. Draw it.",
         _tri("isosceles_triangle", [{"what": "angle", "value": 40}])),
        ("Draw an acute triangle with sides 3 cm, 4 cm and 5 cm.",
         _tri("acute_triangle", [_s(3), _s(4), _s(5)])),
        ("Draw a scalene triangle with sides 5 cm, 5 cm and 6 cm.",
         _tri("scalene_triangle", [_s(5), _s(5), _s(6)])),
        ("Draw an obtuse triangle with angles 50° and 60°.",
         _tri("obtuse_triangle", [{"what": "angle", "value": 50}, {"what": "angle", "value": 60}])),
    ],
)  # fmt: skip
def test_a_triangle_the_reading_does_not_decide_is_not_drawn(question, reading) -> None:
    assert _draw(question, _cm(reading)) is None


def test_an_isosceles_apex_holds_its_angle() -> None:
    question = "Triangle ABC is isosceles with AB = AC and angle A = 40°. Draw it."
    reading = _tri("isosceles_triangle", [{"what": "angle", "name": "A", "value": 40}], "ABC")
    spec = _figure(question, {**reading, "apex": "A"})
    assert angle_at(_at(spec, "A"), _at(spec, "B"), _at(spec, "C")) == pytest.approx(40)
    assert angle_at(_at(spec, "B"), _at(spec, "A"), _at(spec, "C")) == pytest.approx(70)
    assert _side(spec, "A", "B")[2] == _side(spec, "A", "C")[2] == 1


@pytest.mark.parametrize(
    "what, apex", [("apex_angle", 40.0), ("base_angle", 100.0)]
)  # fmt: skip
def test_an_unnamed_isosceles_angle_is_the_one_its_role_says(what: str, apex: float) -> None:
    spec = _figure(
        "An isosceles triangle has a vertex angle of 40°. Draw it."
        if what == "apex_angle"
        else "An isosceles triangle has base angles of 40°. Draw it.",
        _tri("isosceles_triangle", [{"what": what, "value": 40}]),
    )
    top = max(spec.points, key=lambda p: p.y)
    rest = [p for p in spec.points if p.name in spec.faces[0] and p is not top]
    assert angle_at((top.x, top.y), *((p.x, p.y) for p in rest)) == pytest.approx(apex)


def test_named_equal_sides_carry_the_equal_marks() -> None:
    question = "Triangle ABC is isosceles with AB = AC = 7 cm and BC = 4 cm. Draw it."
    spec = _figure(
        question, _cm(_tri("isosceles_triangle", [_s(7, "AB"), _s(7, "AC"), _s(4, "BC")], "ABC"))
    )
    assert _side(spec, "A", "B")[2] == _side(spec, "A", "C")[2] == 1
    assert _side(spec, "B", "C")[1:] == ("4 cm", 0)


def test_an_obtuse_triangle_is_drawn_obtuse() -> None:
    spec = _figure(
        "Draw an obtuse triangle with sides 4 cm and 6 cm.",
        _cm(_tri("obtuse_triangle", [_s(4), _s(6)])),
    )
    corners = [_at(spec, name) for name in spec.faces[0]]
    biggest = max(angle_at(c, *(o for o in corners if o != c)) for c in corners)
    assert biggest > 90


@pytest.mark.parametrize(
    "question, reading, texts",
    [
        # The 5 is a length, never the angle at B.
        ("In triangle ABC, AB = 5 cm, BC = 7 cm and angle B = 50°. Draw it.",
         _cm(_tri("triangle", [_s(5, "AB"), _s(7, "BC"), {"what": "angle", "name": "B", "value": 5}],
                  "ABC")), ()),
        # The 10 of "2x + 10" is a term, no angle.
        ("Parallel lines are cut by a transversal: angles 2x + 10 and 3x - 20 are alternate. Draw it.",
         {"kind": "lines", "shape": "parallel_lines", "measures": [{"what": "angle", "value": 10}]},
         ()),
        ("A rectangle is 2 m long and 50 cm wide. Draw it.",
         _cm({"kind": "polygon", "shape": "rectangle",
              "measures": [_s(2, what="length"), _s(50, what="width")]}), ()),
        ("Plot A(2, 3) and C(-3, -2).",
         {"kind": "points", "points": [{"name": "A", "x": 2, "y": 3},
                                        {"name": "C", "x": 3, "y": -2}]}, ()),
        ("Mark -2.5 and 3/4 on a number line.",
         {"kind": "number_line", "numbers": ["2.5", "3/4"]}, ()),
        ("Sketch f(x) = x^2 - 4 for -3 ≤ x ≤ 3.",
         {"kind": "function", "expr": "x^2 - 4", "x_min": -4, "x_max": 3}, ()),
        ("A regular hexagon has side 8 cm. Draw it.",
         _cm({"kind": "polygon", "shape": "regular_polygon", "sides": 8, "measures": [_s(8)]}), ()),
        # The message states its own numbers: the earlier one's are not its.
        ("Draw a triangle with sides 6 cm and 7 cm.",
         _cm(_tri("triangle", [_s(6), _s(7), _s(5)])), ("A triangle has sides 3, 4 and 5 cm.",)),
    ],
)  # fmt: skip
def test_a_value_must_be_stated_with_its_sign_unit_and_role(question, reading, texts) -> None:
    assert _draw(question, reading, *texts) is None


def test_an_earlier_message_states_the_values_of_draw_it() -> None:
    drawn = _draw(
        "Now draw it.",
        _cm(_tri("triangle", [_s(3), _s(4), _s(5)])),
        "A triangle has sides 3 cm, 4 cm and 5 cm. Find its area.",
    )
    assert drawn is not None


@pytest.mark.parametrize(
    "question, reading, drawn",
    [
        ("Draw the line x = 3.", {"kind": "function", "expr": "3"}, None),
        ("Draw the line y = 3.", {"kind": "function", "expr": "3"}, "3"),
        ("The depth is d = 144 - 4t. Draw the graph for t from 0 to 12.",
         {"kind": "function", "expr": "144 + 4x", "x_min": 0, "x_max": 12}, None),
        ("The depth is d = 144 - 4t. Draw the graph for t from 0 to 12.",
         {"kind": "function", "expr": "144 - 4x", "x_min": 0, "x_max": 12}, "144 - 4t"),
        ("Draw y = 2x + 1 and y = -x + 4 on the same axes.",
         {"kind": "function", "expr": "-x + 4"}, None),
    ],
)  # fmt: skip
def test_a_graph_is_the_whole_formula_the_question_writes(question, reading, drawn) -> None:
    graph = _draw(question, reading)
    if drawn is None:
        assert graph is None
    else:
        assert graph is not None and graph[1]["expr"] == drawn


@pytest.mark.parametrize(
    "question, inequality, drawn",
    [
        ("Show 2x > -3 on a number line.", "x > -3", False),
        ("Show -2 < x <= 3 on a number line.", "x <= 3", False),
        ("Show −2 < x ≤ 3 on a number line.", "-2 < x <= 3", True),
        ("Solve 3x - 5 < 2x + 4 and show the answer on a number line.", "3x - 5 < 2x + 4", True),
    ],
)
def test_an_inequality_is_the_question_s_whole_relation(question, inequality, drawn) -> None:
    line = _draw(question, {"kind": "number_line", "inequality": inequality})
    assert (line is not None) is drawn


def test_whole_number_solutions_are_marked_one_by_one() -> None:
    reading = {"kind": "number_line", "inequality": "-3 < n <= 2", "integers": True}
    line = _draw("Show the integers n with -3 < n ≤ 2 on a number line.", reading)
    assert line is not None
    assert [mark["x"] for mark in line[1]["marks"]] == [-2, -1, 0, 1, 2]


@pytest.mark.parametrize(
    "question, reading",
    [
        ("Triangle ABC is inscribed in a circle with centre O. AB = 6 cm and angle C = 40°. Draw it.",
         {"kind": "circle", "shape": "circle", "center": "O", "inscribed": "triangle",
          "vertices": "ABC", "measures": [_s(6, "AB"), {"what": "angle", "name": "C", "value": 40}]}),
        ("A rectangle 6 cm by 8 cm is inscribed in a circle. Draw it.",
         {"kind": "circle", "shape": "circle", "inscribed": "rectangle",
          "measures": [_s(8, what="length"), _s(6, what="width")]}),
        ("A circle is inscribed in a triangle with sides 3 cm, 4 cm and 5 cm. Draw it.",
         {"kind": "circle", "shape": "circle", "circumscribed": "triangle",
          "measures": [_s(3), _s(4), _s(5)]}),
    ],
)  # fmt: skip
def test_a_shape_with_a_circle_is_drawn_as_stated(question, reading) -> None:
    spec = _figure(question, _cm(reading))
    labels = {s.label for s in spec.segments if s.label} | {a.label for a in spec.angles if a.label}
    stated = {m["value"] for m in reading["measures"]}
    assert {float(label.split()[0].rstrip("°")) for label in labels} == stated
    (arc,) = spec.arcs
    centre = _at(spec, arc.center)
    corners = [_at(spec, name) for name in spec.faces[0]]
    if reading.get("inscribed"):
        assert all(distance(centre, c) == pytest.approx(arc.rx) for c in corners)


@pytest.mark.parametrize(
    "question, shape",
    [
        ("A cone has a diameter of 10 cm and a height of 12 cm. Draw it.", "cone"),
        ("Draw a sphere of diameter 14 cm.", "sphere"),
    ],
)
def test_a_diameter_is_drawn_across_never_on_a_radius(question: str, shape: str) -> None:
    value = 10 if shape == "cone" else 14
    measures = [_s(value, what="diameter")] + ([_s(12, what="height")] if shape == "cone" else [])
    spec = _figure(question, _cm({"kind": "solid", "shape": shape, "measures": measures}))
    segment = next(s for s in spec.segments if s.label == f"{value} cm")
    assert distance(_at(spec, segment.a), _at(spec, segment.b)) == pytest.approx(value)


def test_a_prism_end_shows_only_its_stated_sides() -> None:
    question = (
        "A right triangular prism has a base that is a right triangle with legs 6 cm and 8 cm "
        "and length 12 cm. Draw it."
    )
    measures = [_s(6, what="leg"), _s(8, what="leg"), _s(12, what="length")]
    spec = _figure(
        question, _cm({"kind": "solid", "shape": "triangular_prism", "measures": measures})
    )
    assert sorted(s.label for s in spec.segments if s.label) == ["12 cm", "6 cm", "8 cm"]


@pytest.mark.parametrize(
    "question, reading",
    [
        # Sides 5 and 6 leave the end open: the second 5 is not read.
        ("A triangular prism has an isosceles end with sides 5 cm, 5 cm and base 6 cm, length 10 cm.",
         {"kind": "solid", "shape": "triangular_prism",
          "measures": [_s(5), _s(6, what="base"), _s(10, what="length")]}),
        ("A square pyramid has base 6 cm, height 4 cm and slant height 6 cm. Draw it.",
         {"kind": "solid", "shape": "square_pyramid",
          "measures": [_s(6, what="base"), _s(4, what="height"), _s(6, what="slant_height")]}),
        ("A cuboid has length 8 cm and a square end of side 3 cm. Draw it.",
         {"kind": "solid", "shape": "cuboid", "measures": [_s(8, what="length"), _s(3)]}),
        ("In parallelogram ABCD, angle ACB = 30°. Draw it.",
         {"kind": "polygon", "shape": "parallelogram", "vertices": "ABCD",
          "measures": [{"what": "angle", "name": "ACB", "value": 30}]}),
        ("In rhombus ABCD, angle ABD = 35°. Draw it.",
         {"kind": "polygon", "shape": "rhombus", "vertices": "ABCD",
          "measures": [{"what": "angle", "name": "ABD", "value": 35}]}),
        ("Draw two perpendicular lines and a ray making 40° with one.",
         {"kind": "lines", "shape": "perpendicular_lines", "measures": [{"what": "angle", "value": 40}]}),
        ("Draw a regular hexagon with sides of 5 cm.",
         {"kind": "polygon", "shape": "regular_hexagon", "sides": 5, "measures": [_s(5)]}),
        ("Draw a pentagon whose angles are 100°, 110°, 120°, 90° and 120°.",
         {"kind": "polygon", "shape": "pentagon",
          "measures": [{"what": "angle", "value": v} for v in (100, 110, 120, 90, 120)]}),
        ("A kite has sides 5 cm and 8 cm and one angle of 100°. Draw it.",
         {"kind": "polygon", "shape": "kite",
          "measures": [_s(5), _s(8), {"what": "angle", "value": 100}]}),
        ("A square has side 5 cm. Its diagonal is about 7 cm. Draw it.",
         {"kind": "polygon", "shape": "square", "measures": [_s(5), _s(7, what="diagonal")]}),
        ("A chord of a circle is 3 cm from the centre and the radius is 5 cm. Draw it.",
         {"kind": "circle", "shape": "circle",
          "measures": [_s(5, what="radius"), _s(3, what="length")]}),
    ],
)  # fmt: skip
def test_a_value_the_picture_cannot_honour_draws_nothing(question, reading) -> None:
    assert _draw(question, _cm(reading)) is None


def test_angles_on_a_line_are_each_labelled() -> None:
    spec = _figure(
        "Angles on a straight line are 50°, 60° and x. Draw them.",
        {"kind": "lines", "shape": "angles_on_line",
         "measures": [{"what": "angle", "value": 50}, {"what": "angle", "value": 60}]},
    )  # fmt: skip
    labelled = {mark.label: mark for mark in spec.angles if mark.label}
    assert set(labelled) == {"50°", "60°"}
    for label, mark in labelled.items():
        size = angle_at(_at(spec, mark.at), _at(spec, mark.a), _at(spec, mark.b))
        assert size == pytest.approx(float(label.rstrip("°")))


def test_a_trapezium_s_named_leg_is_the_only_one_labelled() -> None:
    question = "Trapezium ABCD has AB parallel to DC, AB = 10 cm, DC = 6 cm and BC = 5 cm. Draw it."
    measures = [_s(10, "AB", "parallel_side"), _s(6, "DC", "parallel_side"), _s(5, "BC")]
    spec = _figure(question, _cm({"kind": "polygon", "shape": "trapezium", "vertices": "ABCD",
                                  "measures": measures}))  # fmt: skip
    assert _side(spec, "B", "C")[:2] == (pytest.approx(5), "5 cm")
    assert _side(spec, "A", "D")[1:] == (None, 0)


def test_a_trapezium_s_bases_are_its_parallel_sides() -> None:
    question = "A trapezium has bases of 10 cm and 6 cm and a height of 4 cm. Draw it."
    measures = [_s(10, what="base"), _s(6, what="base"), _s(4, what="height")]
    spec = _figure(question, _cm({"kind": "polygon", "shape": "trapezium", "measures": measures}))
    assert sorted(s.label for s in spec.segments if s.label) == ["10 cm", "4 cm", "6 cm"]


def test_a_reading_without_the_unit_takes_the_one_every_length_is_written_in() -> None:
    question = "Triangle PQR is right-angled at Q, PQ = 6 cm and PR = 10 cm. Draw the triangle."
    measures = [
        {"what": "angle", "name": "Q", "value": 90},
        _s(6, "PQ"),
        _s(10, "PR", "hypotenuse"),
    ]
    spec = _figure(question, _tri("right_triangle", measures, "PQR"))
    assert {s.label for s in spec.segments if s.label} == {"6 cm", "10 cm"}
    assert _right_at(spec) == ["Q"]
