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
