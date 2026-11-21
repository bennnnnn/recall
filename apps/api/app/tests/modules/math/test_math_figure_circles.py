"""Circles and their theorems drawn from a question's own values (``math/figure/circle_*``).

The geometry figures corpus (2026-11-20) drew nothing for a sector, a tangent, the angle at
the centre, a cyclic quadrilateral, two crossing chords, a ring, a chord at its distance
from the centre or a triangle's incircle: the read named the circle, but no builder drew
the theorem. Each figure here is held to the question's values where they sit (a labelled
length its length, a labelled angle its size, a theorem's right angle boxed), the asked
value drawn true and unlabelled, and values that cannot hold together draw nothing.
"""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from app.modules.math.figure.build import figure_fence
from app.modules.math.figure.circle_frame import right_triangle
from app.modules.math.figure.drawing import angle_at, distance
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec


def _m(what: str, value: float, name: str = "") -> dict[str, Any]:
    return {"what": what, "value": value, "name": name}


def _draw(question: str, reading: dict[str, Any]) -> FigureSpec | None:
    fence = figure_fence(FigureRequest.model_validate({"kind": "circle", **reading}), [question])
    if fence is None:
        return None
    lang, _, rest = fence.removeprefix("```").partition("\n")
    assert lang == "geometry"
    return FigureSpec.model_validate(json.loads(rest.rsplit("\n```", 1)[0]))


def _figure(question: str, reading: dict[str, Any]) -> FigureSpec:
    spec = _draw(question, reading)
    assert spec is not None
    return spec


def _at(spec: FigureSpec, name: str) -> tuple[float, float]:
    point = next(p for p in spec.points if p.name == name)
    return (point.x, point.y)


def _length(spec: FigureSpec, a: str, b: str) -> float:
    return distance(_at(spec, a), _at(spec, b))


def _angle(spec: FigureSpec, at: str, a: str, b: str) -> float:
    return angle_at(_at(spec, at), _at(spec, a), _at(spec, b))


def _labels(spec: FigureSpec) -> set[str]:
    return {s.label for s in spec.segments if s.label} | {a.label for a in spec.angles if a.label}


def _on_circle(spec: FigureSpec, *names: str) -> bool:
    arc = spec.arcs[0]
    centre = _at(spec, arc.center)
    return all(distance(centre, _at(spec, n)) == pytest.approx(arc.rx) for n in names)


def _shown(spec: FigureSpec) -> set[str]:
    return {p.name for p in spec.points if p.show}


# Sectors, segments and rings.


def test_a_sector_shows_its_radius_and_its_angle_at_the_centre() -> None:
    question = "Find the area of a sector of a circle with radius 9 cm and angle 120°."
    spec = _figure(question, {"shape": "sector", "measures": [_m("radius", 9), _m("angle", 120)]})
    assert _labels(spec) == {"9 cm", "120°"}
    (mark,) = spec.angles
    assert _angle(spec, mark.at, mark.a, mark.b) == pytest.approx(120)
    assert _length(spec, mark.at, mark.a) == pytest.approx(9)
    solid, rest = spec.arcs
    assert solid.end - solid.start == pytest.approx(120) and not solid.dashed
    assert rest.dashed and rest.end - rest.start == pytest.approx(240)


def test_a_segment_adds_the_chord_across_its_sector() -> None:
    question = (
        "A chord subtends 90° at the centre of a circle of radius 8 cm. Find the segment's area."
    )
    spec = _figure(
        question, {"shape": "segment", "measures": [_m("radius", 8), _m("central_angle", 90)]}
    )
    (mark,) = spec.angles
    chord = next(s for s in spec.segments if {s.a, s.b} == {mark.a, mark.b})
    assert chord.label is None
    assert _length(spec, chord.a, chord.b) == pytest.approx(8 * math.sqrt(2))


def test_a_sector_from_a_diameter_draws_the_diameter_across() -> None:
    question = "A wheel of diameter 70 cm turns through an angle of 60°. How far does its rim move?"
    spec = _figure(question, {"shape": "arc", "measures": [_m("diameter", 70), _m("angle", 60)]})
    across = next(s for s in spec.segments if s.label == "70 cm")
    assert _length(spec, across.a, across.b) == pytest.approx(70)


def test_a_sector_named_by_its_angle_is_lettered() -> None:
    question = "In a circle with centre O, angle AOB = 80° and OA = 5 cm. Find the arc AB."
    reading = {"shape": "sector", "center": "O",
               "measures": [_m("radius", 5), _m("central_angle", 80, "AOB")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _shown(spec) == {"A", "B", "O"}
    assert _angle(spec, "O", "A", "B") == pytest.approx(80)


@pytest.mark.parametrize("angle", [240, 400])
def test_a_sector_no_mark_can_show_draws_nothing(angle: float) -> None:
    question = f"A sector of a circle of radius 4 cm has angle {angle}°. Find its area."
    reading = {"shape": "sector", "measures": [_m("radius", 4), _m("central_angle", angle)]}
    assert _draw(question, reading) is None


def test_an_annulus_draws_both_circles_with_their_radii() -> None:
    question = "Find the area of the ring between two circles with the same centre and radii 5 cm and 8 cm."
    spec = _figure(question, {"shape": "annulus", "measures": [_m("radius", 5), _m("radius", 8)]})
    assert sorted(arc.rx for arc in spec.arcs) == [5, 8]
    for label, size in (("5 cm", 5), ("8 cm", 8)):
        radius = next(s for s in spec.segments if s.label == label)
        assert _length(spec, radius.a, radius.b) == pytest.approx(size)


def test_an_annulus_by_its_diameters_draws_them_across() -> None:
    question = "A path runs round a garden of diameter 20 m; its outer edge has diameter 26 m."
    reading = {"shape": "annulus", "unit": "m",
               "measures": [_m("diameter", 20), _m("diameter", 26)]}  # fmt: skip
    spec = _figure(question, reading)
    assert sorted(arc.rx for arc in spec.arcs) == [10, 13]
    assert _labels(spec) == {"20 m", "26 m"}


@pytest.mark.parametrize(
    "measures",
    [[_m("radius", 5), _m("radius", 5)], [_m("radius", 5)], [_m("radius", 5), _m("chord", 8)]],
)
def test_a_ring_needs_two_different_circles(measures: list[dict[str, Any]]) -> None:
    question = "Two circles share a centre, radius 5 cm and 5 cm, with a chord of 8 cm."
    assert _draw(question, {"shape": "annulus", "measures": measures}) is None


# Chords.


def test_a_chord_at_a_distance_draws_the_asked_radius_unlabelled() -> None:
    question = "A chord of length 16 cm is 6 cm from the centre of a circle. Find the radius."
    spec = _figure(question, {"shape": "circle", "measures": [_m("chord", 16), _m("distance", 6)]})
    assert _labels(spec) == {"16 cm", "6 cm"}
    assert spec.arcs[0].rx == pytest.approx(10)
    gap = next(s for s in spec.segments if s.label == "6 cm")
    assert gap.dashed and _length(spec, gap.a, gap.b) == pytest.approx(6)
    radius = next(s for s in spec.segments if s.label is None and not s.dashed)
    assert _length(spec, radius.a, radius.b) == pytest.approx(10)
    assert any(mark.right for mark in spec.angles)


def test_a_chord_from_its_radius_and_distance_is_drawn_to_length() -> None:
    question = "A circle has radius 13 cm. A chord is 5 cm from the centre. Find the chord."
    spec = _figure(question, {"shape": "circle", "measures": [_m("radius", 13), _m("distance", 5)]})
    assert _labels(spec) == {"13 cm", "5 cm"}
    chord = next(s for s in spec.segments if s.label is None and not s.dashed)
    assert _length(spec, chord.a, chord.b) == pytest.approx(24)


def test_a_chord_s_midpoint_is_lettered_as_its_distance_names_it() -> None:
    question = "M is the midpoint of chord PQ of a circle with centre O. OM = 3 cm and PQ = 8 cm."
    reading = {"shape": "circle", "center": "O", "vertices": "PQ",
               "measures": [_m("distance", 3, "OM"), _m("chord", 8, "PQ")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _shown(spec) == set("OMPQ")
    assert _length(spec, "O", "M") == pytest.approx(3)
    assert _length(spec, "O", "Q") == pytest.approx(5)
    assert _angle(spec, "M", "O", "Q") == pytest.approx(90)


@pytest.mark.parametrize(
    "measures",
    [
        [_m("radius", 10), _m("chord", 16), _m("distance", 7)],  # 8-6-10, not 7
        [_m("radius", 5), _m("distance", 5)],  # the chord would be a point
        [_m("distance", 4)],  # nothing sizes the circle
    ],
)
def test_a_chord_that_cannot_sit_at_its_distance_draws_nothing(measures) -> None:
    question = (
        "A circle of radius 10 cm or 5 cm has a chord of 16 cm, 7 cm, 5 cm or 4 cm from the centre."
    )
    assert _draw(question, {"shape": "circle", "measures": measures}) is None


def test_two_chords_cross_by_the_intersecting_chords_theorem() -> None:
    question = (
        "Chords AB and CD of a circle meet at E. AE = 4 cm, EB = 6 cm and CE = 3 cm. Find ED."
    )
    reading = {"shape": "intersecting_chords", "vertices": "ABCD", "point": "E",
               "measures": [_m("length", 4, "AE"), _m("length", 6, "EB"), _m("length", 3, "CE")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _shown(spec) == set("ABCDE")
    assert _length(spec, "E", "D") == pytest.approx(8)
    assert _on_circle(spec, "A", "B", "C", "D")
    assert _angle(spec, "E", "A", "B") == pytest.approx(180)
    assert _angle(spec, "E", "C", "D") == pytest.approx(180)
    asked = next(s for s in spec.segments if {s.a, s.b} == {"E", "D"})
    assert asked.label is None


def test_crossing_chords_from_a_whole_chord_are_worked_out() -> None:
    question = (
        "Chords PQ and RS meet at X. PX = 6 cm, XQ = 4 cm, RS = 11 cm and RX = 3 cm. Find XS."
    )
    reading = {"shape": "intersecting_chords", "vertices": "PQRS", "point": "X",
               "measures": [_m("length", 6, "PX"), _m("length", 4, "XQ"), _m("length", 11, "RS"),
                            _m("length", 3, "RX")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _length(spec, "X", "S") == pytest.approx(8)
    whole = next(s for s in spec.segments if s.label == "11 cm")
    assert {whole.a, whole.b} == {"R", "S"}
    # Both parts of RS asked: it splits by PX·XQ = 24, the longer part first.
    reading["measures"] = reading["measures"][:3]
    spec = _figure(question.replace(" and RX = 3 cm", ""), reading)
    assert sorted([_length(spec, "R", "X"), _length(spec, "X", "S")]) == pytest.approx([3, 8])


@pytest.mark.parametrize(
    "measures",
    [
        [_m("length", 4, "AE"), _m("length", 6, "EB"), _m("length", 3, "CE"), _m("length", 5, "ED")],
        [_m("length", 4, "AE"), _m("length", 6, "EB")],
        [_m("length", 4, "AE"), _m("length", 6, "EB"), _m("length", 3, "CE"), _m("radius", 9)],
    ],
)  # fmt: skip
def test_chord_parts_that_do_not_hold_draw_nothing(measures) -> None:
    question = "Chords AB and CD meet at E. AE = 4, EB = 6, CE = 3, ED = 5, radius 9."
    reading = {
        "shape": "intersecting_chords",
        "vertices": "ABCD",
        "point": "E",
        "measures": measures,
    }
    assert _draw(question, reading) is None


# Tangents.


def test_a_tangent_meets_the_radius_at_a_right_angle() -> None:
    question = (
        "A point P is 13 cm from the centre O of a circle of radius 5 cm. Find the tangent from P."
    )
    reading = {"shape": "tangent", "center": "O", "point": "P",
               "measures": [_m("radius", 5), _m("distance", 13, "OP")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _labels(spec) == {"5 cm", "13 cm"}
    assert _length(spec, "O", "P") == pytest.approx(13)
    (right,) = [mark for mark in spec.angles if mark.right]
    assert _angle(spec, right.at, "O", "P") == pytest.approx(90)
    assert _length(spec, right.at, "P") == pytest.approx(12)
    assert _on_circle(spec, right.at)


def test_a_tangent_from_its_length_and_an_angle() -> None:
    question = "PT touches a circle with centre O at T. OT = 5 cm and angle TPO = 30°. Find OP."
    reading = {"shape": "tangent", "center": "O", "point": "P", "vertices": "T",
               "measures": [_m("radius", 5, "OT"), _m("angle", 30, "TPO")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _length(spec, "O", "P") == pytest.approx(10)
    assert _angle(spec, "P", "T", "O") == pytest.approx(30)
    assert _angle(spec, "T", "O", "P") == pytest.approx(90)


@pytest.mark.parametrize(
    "measures",
    [
        [_m("radius", 5), _m("distance", 4)],  # P inside the circle
        [_m("radius", 5), _m("distance", 13), _m("tangent", 11)],  # 5-12-13
        [_m("radius", 5), _m("angle", 95)],
    ],
)
def test_a_tangent_that_cannot_touch_draws_nothing(measures) -> None:
    question = "A circle of radius 5 cm; P is 4 cm or 13 cm from its centre; tangent 11 cm; 95°."
    assert _draw(question, {"shape": "tangent", "measures": measures}) is None


def test_two_tangents_are_equal_and_meet_the_radii_at_right_angles() -> None:
    question = "Two tangents from T touch a circle with centre O and radius 6 cm. The angle between them is 60°. Find OT."
    reading = {"shape": "two_tangents", "center": "O", "point": "T", "vertices": "AB",
               "measures": [_m("radius", 6), _m("angle", 60, "T")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _labels(spec) == {"6 cm", "60°"}
    assert _length(spec, "O", "T") == pytest.approx(12)
    assert _angle(spec, "T", "A", "B") == pytest.approx(60)
    assert _length(spec, "T", "A") == pytest.approx(_length(spec, "T", "B"))
    assert {s.ticks for s in spec.segments if "T" in (s.a, s.b) and "O" not in (s.a, s.b)} == {1}
    assert {mark.at for mark in spec.angles if mark.right} == {"A", "B"}


def test_two_tangents_from_the_angle_at_the_centre_mark_the_asked_angle() -> None:
    question = "Tangents TA and TB touch a circle with centre O at A and B. Angle AOB = 130°. Find angle ATB."
    reading = {"shape": "two_tangents", "center": "O", "point": "T", "vertices": "AB",
               "measures": [_m("central_angle", 130, "AOB")]}  # fmt: skip
    spec = _figure(question, reading)
    at_t = next(mark for mark in spec.angles if mark.at == "T")
    assert at_t.label is None
    assert _angle(spec, "T", "A", "B") == pytest.approx(50)
    assert _angle(spec, "O", "A", "B") == pytest.approx(130)


def test_two_tangents_whose_angles_disagree_draw_nothing() -> None:
    question = "Tangents from T touch at A and B. Angle ATB = 60° and angle AOB = 100°."
    reading = {"shape": "two_tangents", "center": "O", "point": "T", "vertices": "AB",
               "measures": [_m("angle", 60, "ATB"), _m("central_angle", 100, "AOB")]}  # fmt: skip
    assert _draw(question, reading) is None


@pytest.mark.parametrize(
    "leg, other, hypotenuse, angle, expected",
    [
        (5, None, 13, None, (5, 12, 13)),
        (None, 12, 13, None, (5, 12, 13)),
        (3, 4, None, None, (3, 4, 5)),
        (5, None, None, 30, (5, 5 * math.sqrt(3), 10)),
        (None, None, 10, 30, (5, 5 * math.sqrt(3), 10)),
        (13, None, 5, None, None),
        (5, 12, 14, None, None),
        (5, None, 9, 30, None),
    ],
)
def test_the_right_triangle_a_theorem_draws(leg, other, hypotenuse, angle, expected) -> None:
    found = right_triangle(leg, other, hypotenuse, angle)
    if expected is None:
        assert found is None
    else:
        assert found == pytest.approx(expected)


# Angles in a circle.


def test_the_angle_at_the_centre_is_twice_the_angle_at_the_circumference() -> None:
    question = "The angle at the centre of a circle subtended by an arc is 110°. Find the angle at the circumference."
    spec = _figure(question, {"shape": "angle_at_centre", "measures": [_m("central_angle", 110)]})
    centre = spec.arcs[0].center
    at_o = next(mark for mark in spec.angles if mark.at == centre)
    at_c = next(mark for mark in spec.angles if mark.at != centre)
    assert at_o.label == "110°" and at_c.label is None
    assert _angle(spec, at_c.at, at_c.a, at_c.b) == pytest.approx(55)
    assert _on_circle(spec, at_c.at, at_c.a, at_c.b)


def test_angles_in_the_same_segment_are_both_drawn_true() -> None:
    question = "A, B, C and D lie on a circle, C and D on the same side of AB. Angle ACB = 37°. Find angle ADB."
    reading = {"shape": "angle_at_centre", "vertices": "ABCD",
               "measures": [_m("inscribed_angle", 37, "ACB")]}  # fmt: skip
    spec = _figure(question, reading)
    assert {"A", "B", "C", "D"} <= _shown(spec)
    assert _angle(spec, "C", "A", "B") == pytest.approx(37)
    assert _angle(spec, "D", "A", "B") == pytest.approx(37)
    assert next(m for m in spec.angles if m.at == "D").label is None


def test_an_obtuse_angle_at_the_circumference_leaves_the_reflex_centre_unmarked() -> None:
    question = "An arc subtends 115° at the circumference. Find the reflex angle at the centre."
    spec = _figure(question, {"shape": "angle_at_centre", "measures": [_m("inscribed_angle", 115)]})
    (mark,) = spec.angles
    assert mark.label == "115°"
    assert _angle(spec, mark.at, mark.a, mark.b) == pytest.approx(115)


@pytest.mark.parametrize(
    "measures",
    [
        [_m("central_angle", 100), _m("inscribed_angle", 40)],
        [_m("central_angle", 230)],
        [_m("angle", 50)],  # an angle the read placed nowhere
    ],
)
def test_angles_on_an_arc_that_disagree_draw_nothing(measures) -> None:
    question = "The angle at the centre is 100° or 230° and at the circumference 40° or 50°."
    assert _draw(question, {"shape": "angle_at_centre", "measures": measures}) is None


def test_the_angle_in_a_semicircle_is_right() -> None:
    question = "AB is a diameter of a circle and C is a point on it. AC = 6 cm and BC = 8 cm. Find the radius."
    reading = {"shape": "angle_in_semicircle", "vertices": "ABC",
               "measures": [_m("length", 6, "AC"), _m("length", 8, "BC")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _labels(spec) == {"6 cm", "8 cm"}
    assert _length(spec, "A", "B") == pytest.approx(10)
    assert spec.arcs[0].rx == pytest.approx(5)
    assert _angle(spec, "C", "A", "B") == pytest.approx(90)
    assert next(mark for mark in spec.angles if mark.at == "C").right


def test_the_angle_in_a_semicircle_from_an_angle_and_a_radius() -> None:
    question = (
        "AB is a diameter of a circle of radius 5 cm, C on the circle, angle CAB = 35°. Find BC."
    )
    reading = {"shape": "angle_in_semicircle", "vertices": "ABC",
               "measures": [_m("radius", 5), _m("angle", 35, "CAB")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _angle(spec, "A", "B", "C") == pytest.approx(35)
    assert _angle(spec, "B", "A", "C") == pytest.approx(55)
    radius = next(s for s in spec.segments if s.label == "5 cm")
    assert _length(spec, radius.a, radius.b) == pytest.approx(5)


@pytest.mark.parametrize(
    "measures",
    [
        [_m("length", 6, "AC"), _m("length", 8, "BC"), _m("diameter", 12)],
        [_m("length", 12, "AC"), _m("diameter", 10)],
        [_m("angle", 35, "A"), _m("angle", 50, "B")],
    ],
)
def test_a_triangle_no_semicircle_holds_draws_nothing(measures) -> None:
    question = "AB is a diameter (10 cm or 12 cm), AC = 6 or 12 cm, BC = 8 cm, angles 35° and 50°."
    reading = {"shape": "angle_in_semicircle", "vertices": "ABC", "measures": measures}
    assert _draw(question, reading) is None


def test_a_cyclic_quadrilateral_has_supplementary_opposite_angles() -> None:
    question = (
        "ABCD is a cyclic quadrilateral with angle A = 85° and angle B = 70°. Find angles C and D."
    )
    reading = {"shape": "cyclic_quadrilateral", "vertices": "ABCD",
               "measures": [_m("angle", 85, "A"), _m("angle", 70, "B")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _on_circle(spec, "A", "B", "C", "D")
    for at, a, b, size in (("A", "D", "B", 85), ("B", "A", "C", 70), ("C", "B", "D", 95),
                           ("D", "C", "A", 110)):  # fmt: skip
        assert _angle(spec, at, a, b) == pytest.approx(size)
    assert {m.at: m.label for m in spec.angles} == {"A": "85°", "B": "70°", "C": None, "D": None}


def test_a_cyclic_quadrilateral_from_one_angle_named_by_three_letters() -> None:
    question = "In a cyclic quadrilateral ABCD, angle ABC = 98°. Find angle ADC."
    reading = {"shape": "cyclic_quadrilateral", "vertices": "ABCD",
               "measures": [_m("angle", 98, "ABC")]}  # fmt: skip
    spec = _figure(question, reading)
    assert _angle(spec, "B", "A", "C") == pytest.approx(98)
    assert _angle(spec, "D", "A", "C") == pytest.approx(82)


@pytest.mark.parametrize(
    "measures",
    [
        [_m("angle", 85, "A"), _m("angle", 100, "C")],  # opposite, not 180° together
        [_m("angle", 85, "ABD")],  # a diagonal's angle, not a corner's
        [_m("angle", 85, "A"), _m("side", 4, "AB")],
    ],
)
def test_a_cyclic_quadrilateral_that_cannot_hold_draws_nothing(measures) -> None:
    question = "ABCD is a cyclic quadrilateral: angle A = 85°, angle C = 100°, AB = 4 cm."
    reading = {"shape": "cyclic_quadrilateral", "vertices": "ABCD", "measures": measures}
    assert _draw(question, reading) is None


# A polygon with its circle.


def test_a_triangle_s_incircle_draws_the_asked_radius_unlabelled() -> None:
    question = "Find the radius of the circle inscribed in a right triangle with sides 3 cm, 4 cm and 5 cm."
    reading = {"shape": "circle", "circumscribed": "right_triangle", "parts": ["radius"],
               "measures": [_m("side", 3), _m("side", 4), _m("side", 5)]}  # fmt: skip
    spec = _figure(question, reading)
    assert _labels(spec) == {"3 cm", "4 cm", "5 cm"}
    assert spec.arcs[0].rx == pytest.approx(1)
    radius = next(s for s in spec.segments if spec.arcs[0].center in (s.a, s.b))
    assert radius.label is None and _length(spec, radius.a, radius.b) == pytest.approx(1)


def test_a_circle_inside_a_square_touches_every_side() -> None:
    question = (
        "A circle of radius 5 cm sits inside a square of side 10 cm. Find the area outside it."
    )
    reading = {"shape": "circle", "circumscribed": "square",
               "measures": [_m("radius", 5), _m("side", 10)]}  # fmt: skip
    spec = _figure(question, reading)
    assert _labels(spec) == {"5 cm", "10 cm"}
    assert spec.arcs[0].rx == pytest.approx(5)
    assert (
        _draw(
            question.replace("5 cm", "4 cm"),
            {**reading, "measures": [_m("radius", 4), _m("side", 10)]},
        )
        is None
    )


def test_a_theorem_s_right_angle_needs_no_digits() -> None:
    question = "AB is a diameter and C lies on the circle. AC = 6 cm and BC = 8 cm. Find AB."
    reading = {"shape": "angle_in_semicircle", "vertices": "ABC",
               "measures": [_m("length", 6, "AC"), _m("length", 8, "BC"), _m("angle", 90, "C")]}  # fmt: skip
    spec = _figure(question, reading)
    assert next(mark for mark in spec.angles if mark.at == "C").right


@pytest.mark.parametrize(
    "named, inscribed, circumscribed",
    [
        ({"circle_through": "rectangle"}, "rectangle", ""),
        ({"circle_within": "right_triangle"}, "", "right_triangle"),
        # The read's names by where the circle is win over the builders' own.
        ({"circle_within": "square", "inscribed": "square"}, "", "square"),
    ],
)
def test_a_shape_with_a_circle_is_read_by_where_the_circle_is(
    named: dict[str, str], inscribed: str, circumscribed: str
) -> None:
    request = FigureRequest.model_validate({"kind": "circle", **named})
    assert (request.inscribed, request.circumscribed) == (inscribed, circumscribed)
    again = FigureRequest.model_validate_json(request.model_dump_json())
    assert (again.inscribed, again.circumscribed) == (inscribed, circumscribed)


def test_the_circle_through_a_rectangle_s_corners_is_its_circumcircle() -> None:
    question = (
        "Find the radius of the circle that passes through the corners of a rectangle 6 cm by 8 cm."
    )
    reading = {"shape": "circle", "circle_through": "rectangle", "parts": ["radius"],
               "measures": [_m("length", 8), _m("width", 6)]}  # fmt: skip
    spec = _figure(question, reading)
    assert spec.arcs[0].rx == pytest.approx(5)
    assert _on_circle(spec, *spec.faces[0])
