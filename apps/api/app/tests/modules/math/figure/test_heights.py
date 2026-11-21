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


def test_heights_a_triangles_base_is_the_scenes_ground() -> None:
    reading = _scene("right_triangle", ("length", 10), ("base", 6))
    spec = figure(LADDER, reading)
    assert labels(spec) == ["10 m", "6 m"]
    assert _top(spec) == pytest.approx(8)


def _measured(shape: str, *measures: tuple[str, float, str], **more: Any) -> dict[str, Any]:
    reading = _scene(shape, **more)
    reading["measures"] = [{"what": w, "value": v, "of": of} for w, v, of in measures]
    return reading


OPPOSITE = (
    "The angles of elevation of the top of a tower from two points on opposite sides of it "
    "are 30° and 60°. The tower is 50 m high. Find the distance between the points."
)


@pytest.mark.parametrize("parts", [[], ["opposite_sides"]])
def test_heights_two_points_on_opposite_sides_stand_either_side_of_the_foot(
    parts: list[str],
) -> None:
    reading = _scene("elevation", ("angle", 30), ("angle", 60), ("height", 50))
    spec = figure(OPPOSITE, {**reading, "parts": parts})
    assert spec.shape == "elevation_opposite_sides"
    assert labels(spec) == ["30°", "50 m", "60°"]
    assert labelled_length(spec, "50 m") == pytest.approx(50)
    assert labelled_angle(spec, "30°") == pytest.approx(30)
    assert labelled_angle(spec, "60°") == pytest.approx(60)
    ground = sorted(p.x for p in spec.points if p.y == 0 and p.x != 0)
    assert ground == pytest.approx([-50 * math.sqrt(3), 50 / math.sqrt(3)])


def test_heights_opposite_sides_gap_decides_the_height_by_the_sum_of_cotangents() -> None:
    question = (
        "Two points on opposite sides of a tower are 100 m apart. The angles of elevation of "
        "its top from them are 30° and 60°. Find the height of the tower."
    )
    spec = figure(question, _scene("elevation", ("angle", 30), ("angle", 60), ("gap", 100)))
    assert labelled_length(spec, "100 m") == pytest.approx(100)
    # h (cot 30° + cot 60°) = 100.
    assert _top(spec) == pytest.approx(100 / (math.sqrt(3) + 1 / math.sqrt(3)))
    assert labels(spec) == ["100 m", "30°", "60°"]


def test_heights_opposite_sides_of_a_lighthouse_seen_down_from_its_top() -> None:
    question = (
        "From the top of a 75 m lighthouse, the angles of depression of two ships on opposite "
        "sides of it are 30° and 45°."
    )
    spec = figure(question, _scene("depression", ("angle", 30), ("angle", 45), ("height", 75)))
    assert labelled_angle(spec, "30°") == pytest.approx(30)
    assert labelled_angle(spec, "45°") == pytest.approx(45)
    ground = sorted(p.x for p in spec.points if p.y == 0 and p.x != 0)
    assert ground == pytest.approx([-75 * math.sqrt(3), 75])


@pytest.mark.parametrize(
    ("question", "parts", "shape"),
    [
        # The read says opposite sides; the question says none: one side.
        ("From two points 20 m apart, the angles of elevation of a tower are 30° and 60°.",
         ["opposite_sides"], "elevation_two_points"),
        # The read says opposite sides; the question says the same side.
        ("From two points 20 m apart on the same side of a tower, the angles of elevation are "
         "30° and 60°.", ["opposite_sides"], "elevation_two_points"),
        # The read says one side; the question says opposite sides.
        ("From two points 20 m apart on opposite sides of a tower, the angles of elevation "
         "are 30° and 60°.", ["same_side"], "elevation_opposite_sides"),
    ],
)  # fmt: skip
def test_heights_two_points_stand_on_the_side_the_question_says_never_the_read(
    question: str, parts: list[str], shape: str
) -> None:
    reading = _scene("elevation", ("angle", 30), ("angle", 60), ("gap", 20))
    assert figure(question, {**reading, "parts": parts}).shape == shape


def test_heights_two_points_on_both_sides_said_draw_nothing() -> None:
    question = (
        "From two points 20 m apart, on the same side or on opposite sides of a tower, the "
        "angles of elevation are 30° and 60°."
    )
    assert draw(question, _scene("elevation", ("angle", 30), ("angle", 60), ("gap", 20))) is None


MAN = (
    "A man 1.6 m tall stands 20 m from a tower. The angle of elevation of the top of the "
    "tower from his eyes is 30°. Find the height of the tower."
)


@pytest.mark.parametrize("of", ["man", "observer"])
def test_heights_an_observers_eye_height_is_his_not_the_towers(of: str) -> None:
    reading = _measured("elevation", ("height", 1.6, of), ("distance", 20, ""), ("angle", 30, ""))
    spec = figure(MAN, reading)
    assert spec.shape == "elevation_observer"
    assert labels(spec) == ["1.6 m", "20 m", "30°"]
    assert labelled_length(spec, "1.6 m") == pytest.approx(1.6)
    assert labelled_length(spec, "20 m") == pytest.approx(20)
    assert labelled_angle(spec, "30°") == pytest.approx(30)
    # The tower: his eye height and the rise above it, 20 tan 30°.
    assert _top(spec) == pytest.approx(1.6 + 20 * math.tan(math.radians(30)))
    mark = next(a for a in spec.angles if a.label == "30°")
    assert at(spec, mark.at) == pytest.approx((20, 1.6))


def test_heights_an_observer_and_an_angle_alone_never_label_the_tower() -> None:
    question = "A 1.6 m tall man sees the top of a tower at an angle of elevation of 30°."
    spec = figure(question, _measured("elevation", ("height", 1.6, "man"), ("angle", 30, "")))
    assert labelled_length(spec, "1.6 m") == pytest.approx(1.6)
    assert _top(spec) > 1.6


def test_heights_an_observer_taller_than_the_tower_draws_nothing() -> None:
    question = "A man 1.8 m tall sees the top of a 1.5 m wall at 30° from 2 m away."
    reading = _measured(
        "elevation", ("height", 1.8, "man"), ("height", 1.5, "wall"), ("angle", 30, "")
    )
    assert draw(question, reading) is None


@pytest.mark.parametrize(
    "measures",
    [
        # A flagstaff on a building: two things standing up.
        [("height", 20, "building"), ("height", 5, "flagstaff"), ("angle", 45, "")],
        # Seen from one point: the bottom and the top of the flagstaff.
        [("height", 20, "building"), ("angle", 45, ""), ("angle", 60, "")],
    ],
)
def test_heights_two_tops_seen_from_one_point_draw_nothing(
    measures: list[tuple[str, float, str]],
) -> None:
    question = (
        "From a point on the ground, the angles of elevation of the bottom and the top of a "
        "5 m flagstaff on a 20 m building are 45° and 60°."
    )
    assert draw(question, _measured("elevation", *measures)) is None
