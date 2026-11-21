"""Heights and distances drawn as the right triangle in its scene, true to the stated
values, and nothing drawn when the values cannot hold."""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.modules.math.figure.heights import build_scene
from app.modules.math.figure.request import FigureRequest

from .figure_support import at, draw, figure, labelled_angle, labelled_length, labels

TOWER = (
    "From a point 50 m from the foot of a tower, the angle of elevation of the top of the "
    "tower is 35°. Find the height of the tower."
)
LADDER = "A 10 m ladder leans against a vertical wall with its foot 6 m from the wall."
CLIFF = "From the top of an 80 m cliff, the angle of depression of a boat is 25°."
KITE = "A kite is flying on a 60 m string that makes an angle of 50° with the ground."


def _scene(shape: str, *measures: tuple[str, float], unit: str = "m") -> dict[str, Any]:
    return {
        "kind": "polygon",
        "shape": shape,
        "measures": [{"what": what, "value": value} for what, value in measures],
        "unit": unit,
    }


def _top(spec: Any) -> float:
    return max(p.y for p in spec.points)


def test_heights_elevation_draws_the_tower_to_its_worked_height() -> None:
    spec = figure(TOWER, _scene("elevation", ("distance", 50), ("angle", 35)))
    assert labels(spec) == ["35°", "50 m"]
    assert labelled_length(spec, "50 m") == pytest.approx(50)
    assert labelled_angle(spec, "35°") == pytest.approx(35)
    assert _top(spec) == pytest.approx(50 * math.tan(math.radians(35)))
    assert any(mark.right for mark in spec.angles)


def test_heights_ladder_reaches_the_height_its_length_decides() -> None:
    spec = figure(LADDER, _scene("leaning", ("length", 10), ("distance", 6)))
    assert labels(spec) == ["10 m", "6 m"]
    assert labelled_length(spec, "10 m") == pytest.approx(10)
    ladder = next(s for s in spec.segments if s.label == "10 m")
    assert max(at(spec, ladder.a)[1], at(spec, ladder.b)[1]) == pytest.approx(8)


def test_heights_depression_marks_the_angle_below_the_dashed_horizontal() -> None:
    spec = figure(CLIFF, _scene("depression", ("height", 80), ("angle", 25)))
    assert labelled_length(spec, "80 m") == pytest.approx(80)
    assert labelled_angle(spec, "25°") == pytest.approx(25)
    mark = next(a for a in spec.angles if a.label == "25°")
    level = next(s for s in spec.segments if s.dashed)
    assert mark.at in {level.a, level.b} and mark.a in {level.a, level.b}
    assert at(spec, mark.b) == pytest.approx((80 / math.tan(math.radians(25)), 0.0))


def test_heights_kite_string_has_its_height_dashed() -> None:
    spec = figure(KITE, _scene("slope", ("length", 60), ("angle", 50)))
    assert labels(spec) == ["50°", "60 m"]
    upright = [s for s in spec.segments if s.dashed]
    assert len(upright) == 1
    assert _top(spec) == pytest.approx(60 * math.sin(math.radians(50)))


def test_heights_angle_with_the_wall_sits_at_the_top() -> None:
    question = "A 5 m ladder leans on a wall, making an angle of 20° with the wall."
    spec = figure(question, _scene("leaning", ("length", 5), ("angle_from_vertical", 20)))
    assert labelled_angle(spec, "20°") == pytest.approx(20)
    mark = next(a for a in spec.angles if a.label == "20°")
    assert next(p for p in spec.points if p.name == mark.at).x == pytest.approx(0)


def test_heights_two_points_give_the_height_both_angles_hold() -> None:
    question = "From two points 20 m apart, the angles of elevation of a tower are 30° and 60°."
    spec = figure(question, _scene("elevation", ("angle", 30), ("angle", 60), ("gap", 20)))
    assert labels(spec) == ["20 m", "30°", "60°"]
    assert labelled_length(spec, "20 m") == pytest.approx(20)
    assert labelled_angle(spec, "30°") == pytest.approx(30)
    assert labelled_angle(spec, "60°") == pytest.approx(60)
    assert _top(spec) == pytest.approx(20 / (math.sqrt(3) - 1 / math.sqrt(3)))


def test_heights_a_triangle_read_by_scene_roles_is_drawn_as_the_scene() -> None:
    question = "A 15 m wire runs from the top of a pole to the ground 9 m from its foot."
    reading = _scene("right_triangle", ("length", 15), ("distance", 9))
    spec = figure(question, reading)
    assert spec.shape == "elevation"
    assert _top(spec) == pytest.approx(12)


@pytest.mark.parametrize(
    ("question", "measures"),
    [
        ("A 5 m ladder stands 6 m from a wall.", [("length", 5), ("distance", 6)]),
        (
            "A tower 3 m high, 4 m away, sight line 6 m.",
            [("height", 3), ("distance", 4), ("length", 6)],
        ),
        ("The angle of elevation is 95° from 10 m away.", [("angle", 95), ("distance", 10)]),
        (
            "Angles of 30° and 60° are seen 10 m from the tower.",
            [("angle", 30), ("angle", 60), ("distance", 10)],
        ),
    ],
)
def test_heights_values_that_cannot_hold_draw_nothing(
    question: str, measures: list[tuple[str, float]]
) -> None:
    assert draw(question, _scene("elevation", *measures)) is None


def test_heights_an_unknown_scene_draws_nothing() -> None:
    request = FigureRequest.model_validate(_scene("balloon", ("height", 3)))
    assert build_scene(request) is None
