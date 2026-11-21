"""A right triangle's altitude to its hypotenuse, an isosceles trapezium by its equal sides,
and two circles with different centres: each drawn true to its stated values, worked ones
unlabelled, or not at all (the hard-geometry round, 2026-11-21)."""

from __future__ import annotations

from typing import Any

import pytest

from .figure_support import at, draw, figure, labelled_length, labels, length


def _reading(kind: str, shape: str, *measures: tuple[str, float], **more: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "shape": shape,
        "unit": "cm",
        "measures": [{"what": w, "value": v} for w, v in measures],
        **more,
    }


ALTITUDE = (
    "A right-angled triangle has a hypotenuse of 25 cm. The altitude from the right angle "
    "divides the hypotenuse into two segments of 9 cm and 16 cm. Find the altitude."
)


def test_altitude_split_draws_the_parts_the_altitude_and_both_right_angles() -> None:
    reading = _reading(
        "polygon", "right_triangle", ("hypotenuse", 25), ("length", 9), ("length", 16)
    )
    spec = figure(ALTITUDE, reading)
    assert labels(spec) == ["16 cm", "25 cm", "9 cm"]
    assert labelled_length(spec, "9 cm") == pytest.approx(9)
    assert labelled_length(spec, "16 cm") == pytest.approx(16)
    assert labelled_length(spec, "25 cm") == pytest.approx(25)
    # The worked altitude (12) and legs (15, 20) are drawn to size, unlabelled.
    assert length(spec, "C", "D") == pytest.approx(12)
    assert sorted([length(spec, "A", "C"), length(spec, "B", "C")]) == pytest.approx([15, 20])
    assert sum(mark.right for mark in spec.angles) == 2
    assert next(s for s in spec.segments if {s.a, s.b} == {"C", "D"}).dashed


@pytest.mark.parametrize(
    ("question", "measures", "corner", "hypotenuse"),
    [
        (
            "In a right triangle the legs are 6 cm and 8 cm. Find the altitude to the hypotenuse.",
            [("leg", 6), ("leg", 8)],
            (3.6, 4.8),
            10,
        ),
        (
            "A right triangle has hypotenuse 10 cm and the altitude to the hypotenuse is 4.8 cm.",
            [("hypotenuse", 10), ("height", 4.8)],
            (3.6, 4.8),
            10,
        ),
        (
            "The altitude to the hypotenuse of a right triangle is 6 cm and cuts off a part 4 cm long.",
            [("height", 6), ("length", 4)],
            (4, 6),
            13,
        ),
    ],
)
def test_any_two_values_decide_the_altitude_figure(
    question: str,
    measures: list[tuple[str, float]],
    corner: tuple[float, float],
    hypotenuse: float,
) -> None:
    spec = figure(question, _reading("polygon", "right_triangle", *measures))
    assert at(spec, "C") == pytest.approx(corner)
    assert length(spec, "A", "B") == pytest.approx(hypotenuse)
    assert len(labels(spec)) == len(measures)


def test_altitude_lettered_as_the_question_letters_it() -> None:
    question = (
        "In triangle ABC, angle C = 90°, CD is the altitude to the hypotenuse AB, AD = 4 cm "
        "and DB = 9 cm. Find CD."
    )
    reading = {
        "kind": "polygon",
        "shape": "right_triangle",
        "vertices": "ABC",
        "unit": "cm",
        "measures": [
            {"what": "angle", "name": "C", "value": 90},
            {"what": "length", "name": "AD", "value": 4},
            {"what": "length", "name": "DB", "value": 9},
        ],
    }
    spec = figure(question, reading)
    assert {p.name for p in spec.points if p.show} == {"A", "B", "C", "D"}
    assert length(spec, "C", "D") == pytest.approx(6)
    assert next(s for s in spec.segments if {s.a, s.b} == {"A", "D"}).label == "4 cm"


@pytest.mark.parametrize(
    ("question", "measures"),
    [
        # A leg and a part: beside each other or not, two different triangles.
        (
            "In a right triangle a leg is 15 cm and the altitude to the hypotenuse cuts off 9 cm.",
            [("leg", 15), ("length", 9)],
        ),
        # Parts that do not add up to the hypotenuse.
        (
            "A right triangle has hypotenuse 25 cm; the altitude cuts the hypotenuse into 9 cm and 15 cm.",
            [("hypotenuse", 25), ("length", 9), ("length", 15)],
        ),
        # An altitude longer than half the hypotenuse.
        (
            "A right triangle has hypotenuse 10 cm and its altitude to the hypotenuse is 6 cm.",
            [("hypotenuse", 10), ("height", 6)],
        ),
    ],
)
def test_altitude_values_that_cannot_hold_or_leave_it_open_draw_nothing(
    question: str, measures: list[tuple[str, float]]
) -> None:
    assert draw(question, _reading("polygon", "right_triangle", *measures)) is None


def test_altitude_exactly_half_the_hypotenuse_is_the_isosceles_right_triangle() -> None:
    question = "A right triangle has hypotenuse 10 cm and its altitude to the hypotenuse is 5 cm."
    spec = figure(
        question, _reading("polygon", "right_triangle", ("hypotenuse", 10), ("height", 5))
    )
    assert at(spec, "C") == pytest.approx((5, 5), abs=1e-4)


@pytest.mark.parametrize(
    ("question", "shape", "measures", "corners"),
    [
        (
            "An isosceles trapezoid has parallel sides of 20 cm and 12 cm, and equal non-parallel "
            "sides of 5 cm. Find its height.",
            "trapezium",
            [("parallel_side", 20), ("parallel_side", 12), ("equal_side", 5)],
            [(0, 0), (20, 0), (16, 3), (4, 3)],
        ),
        (
            "A trapezium has parallel sides 8 cm and 20 cm and its equal sides are 10 cm and 10 cm.",
            "trapezium",
            [("parallel_side", 8), ("parallel_side", 20), ("equal_side", 10), ("equal_side", 10)],
            [(0, 0), (20, 0), (14, 8), (6, 8)],
        ),
        (
            "An isosceles trapezium has parallel sides of 10 cm and 16 cm and slanting sides of 5 cm.",
            "isosceles_trapezium",
            [("parallel_side", 10), ("parallel_side", 16), ("leg", 5)],
            [(0, 0), (16, 0), (13, 4), (3, 4)],
        ),
    ],
)
def test_isosceles_trapezium_from_its_equal_sides(
    question: str,
    shape: str,
    measures: list[tuple[str, float]],
    corners: list[tuple[float, float]],
) -> None:
    spec = figure(question, _reading("polygon", shape, *measures))
    assert [at(spec, name) for name in "ABCD"] == [pytest.approx(c) for c in corners]
    legs = [s for s in spec.segments if {s.a, s.b} in ({"B", "C"}, {"D", "A"})]
    assert [s.ticks for s in legs] == [1, 1]
    assert not any(s.dashed for s in spec.segments)  # the worked height is not drawn as stated


def test_trapezium_the_question_calls_isosceles_has_equal_legs() -> None:
    question = (
        "The non-parallel sides of an isosceles trapezium are each 10 cm long and its parallel "
        "sides are 8 cm and 20 cm. Find its area."
    )
    reading = _reading(
        "polygon", "trapezium", ("leg", 10), ("parallel_side", 8), ("parallel_side", 20)
    )
    spec = figure(question, reading)
    assert length(spec, "B", "C") == pytest.approx(length(spec, "A", "D")) == pytest.approx(10)
    assert at(spec, "D")[1] == pytest.approx(8)


def test_isosceles_trapezium_with_legs_too_short_draws_nothing() -> None:
    question = (
        "An isosceles trapezium has parallel sides of 20 cm and 12 cm and equal sides of 3 cm."
    )
    reading = _reading(
        "polygon", "trapezium", ("parallel_side", 20), ("parallel_side", 12), ("equal_side", 3)
    )
    assert draw(question, reading) is None


TWO = (
    "Two circles have radii 13 cm and 15 cm. The distance between their centers is 14 cm. "
    "Find the length of their common chord."
)


@pytest.mark.parametrize("shape", ["intersecting_chords", "two_circles", "circle"])
def test_two_circles_and_their_common_chord(shape: str) -> None:
    reading = _reading("circle", shape, ("radius", 13), ("radius", 15), ("distance", 14))
    spec = figure(TWO, reading)
    assert spec.shape == "two_circles"
    assert sorted(arc.rx for arc in spec.arcs) == [13, 15]
    assert labels(spec) == ["13 cm", "14 cm", "15 cm"]
    chord = next(s for s in spec.segments if s.label is None and not s.dashed)
    assert length(spec, chord.a, chord.b) == pytest.approx(24)  # worked, unlabelled
    assert any(mark.right for mark in spec.angles)


@pytest.mark.parametrize(
    ("question", "measures", "centres"),
    [
        (
            "Two circles of radii 10 cm and 17 cm intersect and their common chord is 16 cm "
            "long. Find the distance between their centres.",
            [("radius", 10), ("radius", 17), ("chord", 16)],
            21,
        ),
        (
            "Two circles of radii 4 cm and 6 cm touch each other externally. Find the distance "
            "between their centres.",
            [("radius", 4), ("radius", 6)],
            10,
        ),
        (
            "Two circles of radii 4 cm and 6 cm touch internally. Find the distance between "
            "their centres.",
            [("radius", 4), ("radius", 6)],
            2,
        ),
        (
            "Two circles of radii 3 cm and 4 cm have centres 12 cm apart. Find the length of "
            "their direct common tangent.",
            [("radius", 3), ("radius", 4), ("distance", 12)],
            12,
        ),
    ],
)
def test_two_circles_centres_apart_as_the_question_decides(
    question: str, measures: list[tuple[str, float]], centres: float
) -> None:
    spec = figure(question, _reading("circle", "two_circles", *measures))
    dots = [p for p in spec.points if p.dot]
    assert abs(dots[1].x - dots[0].x) == pytest.approx(centres)
    assert len(labels(spec)) == len(measures)


def test_touching_circles_read_as_a_ring_are_two_circles() -> None:
    question = "Two circles of radii 4 cm and 6 cm touch each other externally."
    spec = figure(question, _reading("circle", "annulus", ("radius", 4), ("radius", 6)))
    assert spec.shape == "two_circles"


@pytest.mark.parametrize(
    ("question", "measures"),
    [
        # Neither a distance, a chord nor touching: they may cross, touch or lie apart.
        ("Two circles have radii 4 cm and 6 cm. Find the difference of their areas.",
         [("radius", 4), ("radius", 6)]),
        # A common chord longer than the smaller circle's diameter.
        ("Two circles of radii 4 cm and 6 cm have a common chord of 10 cm.",
         [("radius", 4), ("radius", 6), ("chord", 10)]),
        # A common chord of circles that never meet.
        ("Two circles of radii 3 cm and 4 cm, centres 12 cm apart, have a common chord 2 cm.",
         [("radius", 3), ("radius", 4), ("distance", 12), ("chord", 2)]),
    ],
)  # fmt: skip
def test_two_circles_that_cannot_hold_draw_nothing(
    question: str, measures: list[tuple[str, float]]
) -> None:
    assert draw(question, _reading("circle", "two_circles", *measures)) is None


def test_a_ring_is_still_two_circles_about_one_centre() -> None:
    question = "Find the area of the ring between two circles with the same centre and radii 5 cm and 8 cm."
    spec = figure(question, _reading("circle", "annulus", ("radius", 5), ("radius", 8)))
    assert spec.shape == "annulus"
