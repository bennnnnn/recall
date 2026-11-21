"""Circle figures drawn as the question states them: a semicircle by itself is its arc on its
diameter (never a whole circle with a triangle in it), and two crossing chords carry a
stated angle where the question names it."""

from __future__ import annotations

from typing import Any

import pytest

from .figure_support import angle, at, draw, figure, labelled_length, labels, length


def _semicircle(*measures: tuple[str, float], **extra: Any) -> dict[str, Any]:
    return {
        "kind": "circle",
        "shape": "semicircle",
        "unit": "cm",
        "measures": [{"what": what, "value": value} for what, value in measures],
        **extra,
    }


def test_circle_figures_a_semicircle_by_its_radius_is_half_a_circle_on_its_diameter() -> None:
    spec = figure("A semicircle has radius 7 cm. Find its perimeter.", _semicircle(("radius", 7)))
    assert spec.shape == "semicircle"
    assert labels(spec) == ["7 cm"]
    assert labelled_length(spec, "7 cm") == pytest.approx(7)
    (arc,) = spec.arcs
    assert (arc.rx, arc.start, arc.end) == (pytest.approx(7), 0.0, 180.0)
    diameter = [s for s in spec.segments if length(spec, s.a, s.b) == pytest.approx(14)]
    assert len(diameter) == 1
    # No point on the arc, no triangle: the diameter and the radius only.
    assert len(spec.segments) == 2
    assert not spec.angles


def test_circle_figures_a_semicircle_by_its_diameter_labels_the_diameter() -> None:
    question = "A semicircle AB has diameter 10 cm. Find its area."
    spec = figure(question, _semicircle(("diameter", 10), vertices="AB"))
    assert labels(spec) == ["10 cm"]
    assert length(spec, "A", "B") == pytest.approx(10)
    assert at(spec, "A") == pytest.approx((-5.0, 0.0))


def test_circle_figures_a_semicircle_with_a_point_on_it_is_the_theorem() -> None:
    question = "AB is a diameter of a semicircle and C is a point on it. Angle CAB = 35°."
    reading = {
        "kind": "circle",
        "shape": "semicircle",
        "vertices": "ABC",
        "measures": [{"what": "angle", "name": "CAB", "value": 35}],
    }
    spec = figure(question, reading)
    assert spec.shape == "circle_semicircle_angle"
    assert angle(spec, "C", "A", "B") == pytest.approx(90)
    assert angle(spec, "A", "C", "B") == pytest.approx(35)


def test_circle_figures_a_semicircle_with_another_value_draws_nothing() -> None:
    question = "A semicircle has radius 7 cm and perimeter 36 cm."
    assert draw(question, _semicircle(("radius", 7), ("perimeter", 36))) is None


def _chords(angle_name: str, value: float) -> dict[str, Any]:
    return {
        "kind": "circle",
        "shape": "intersecting_chords",
        "point": "E",
        "vertices": "ABCD",
        "unit": "cm",
        "measures": [
            {"what": "length", "name": "AE", "value": 4},
            {"what": "length", "name": "EB", "value": 6},
            {"what": "length", "name": "CE", "value": 3},
            {"what": "angle", "name": angle_name, "value": value},
        ],
    }


@pytest.mark.parametrize("name", ["AED", "BEC", "BED", "AEC"])
def test_circle_figures_crossing_chords_mark_the_stated_angle_where_it_is(name: str) -> None:
    question = (
        f"Chords AB and CD of a circle meet at E. AE = 4 cm, EB = 6 cm, CE = 3 cm and angle "
        f"{name} = 70°. Find ED."
    )
    spec = figure(question, _chords(name, 70))
    (mark,) = spec.angles
    assert (mark.at, {mark.a, mark.b}, mark.label) == ("E", {name[0], name[2]}, "70°")
    assert angle(spec, "E", name[0], name[2]) == pytest.approx(70)
    # The chords' parts true: AE·EB = CE·ED.
    assert length(spec, "E", "D") == pytest.approx(8)


def test_circle_figures_an_angle_along_one_chord_draws_nothing() -> None:
    question = "Chords AB and CD meet at E. AE = 4 cm, EB = 6 cm, CE = 3 cm, angle AEB = 70°."
    assert draw(question, _chords("AEB", 70)) is None
