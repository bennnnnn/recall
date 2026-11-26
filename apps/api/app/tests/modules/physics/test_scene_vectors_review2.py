"""Arrows a physics reply describes, in the cases review round 2 of #2593 found. The rule:
a direction, a mass or a name goes to a value only when the question ties them for sure;
when it does not, nothing is drawn, never a wrong picture."""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from app.modules.physics.scene_drawing.values import Stated
from app.modules.physics.scene_drawing.vectors import described_vectors
from app.modules.physics.schemas import SimulationBlockSpec

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")


def _drawn(
    question: str, layout: str, quantity: str, arrows: list[dict[str, str]], **more: Any
) -> list[SimulationBlockSpec]:
    body = {"kind": "vectors", "layout": layout, "quantity": quantity, "arrows": arrows, **more}
    return described_vectors(json.dumps(body), [question])


def _arrow(size: str, direction: str | None = None, **more: str) -> dict[str, str]:
    return {"size": size, **({"direction": direction} if direction else {}), **more}


def _angles(spec: SimulationBlockSpec) -> list[int]:
    return [round(math.degrees(math.atan2(v.dy, v.dx)) % 360.0) for v in spec.vectors]


def test_a_westerly_direction_is_the_way_a_body_goes() -> None:
    """ "in a westerly direction" is west; only a westerly wind blows from the west, and a
    bare "westerly" is unread."""
    ship = "A ship sails in a westerly direction at 12 km/h. Draw its velocity."
    (spec,) = _drawn(ship, "tail", "velocity", [_arrow("12 km/h", "west")])
    assert _angles(spec) == [180]
    assert _drawn(ship, "tail", "velocity", [_arrow("12 km/h", "east")]) == []
    bare = "A westerly blows at 12 km/h. Draw its velocity."
    for way in ("east", "west"):
        assert _drawn(bare, "tail", "velocity", [_arrow("12 km/h", way)]) == []
    wind = "A westerly wind blows at 12 km/h. Draw its velocity."
    (spec,) = _drawn(wind, "tail", "velocity", [_arrow("12 km/h", "east")])
    assert _angles(spec) == [0]


def test_a_side_and_an_angle_above_the_horizontal_are_one_heading() -> None:
    sled = "A rope pulls a sled to the left with a force of 40 N at 30° above the horizontal."
    assert _drawn(sled, "tail", "force", [_arrow("40 N", "30° above the horizontal")]) == []
    (spec,) = _drawn(
        sled, "tail", "force", [_arrow("40 N", "30° above the horizontal to the left")]
    )
    assert _angles(spec) == [150]


def test_two_ways_for_one_value_draw_nothing() -> None:
    both = "A ball moves north at 3 m/s and then, without slowing, east. Draw its velocity."
    torn = "A cart is pushed due north and due east at 3 m/s. Draw its velocity."
    assert _drawn(torn, "tail", "velocity", [_arrow("3 m/s", "north")]) == []
    assert _drawn(both, "tail", "velocity", [_arrow("3 m/s", "east")]) == []


def test_a_direction_goes_to_the_value_of_its_own_kind() -> None:
    """ "a car travelling north at 20 m/s brakes with a force of 5000 N": north is the car's,
    and the force's way is unstated, so no force picture is drawn."""
    brake = "A car travelling north at 20 m/s brakes with a force of 5000 N. Draw the force."
    assert _drawn(brake, "tail", "force", [_arrow("5000 N", "north")]) == []
    assert _drawn(brake, "tail", "force", [_arrow("5000 N", "south")]) == []


@pytest.mark.parametrize(
    "written", ["a wind from the west", "a gale from the west", "from the west", "a west wind"]
)
def test_the_contracts_own_wording_is_read(written: str) -> None:
    plane = "A plane flies due north at 200 km/h. The wind blows from the west at 50 km/h."
    (spec,) = _drawn(
        plane, "tail", "velocity", [_arrow("200 km/h", "north"), _arrow("50 km/h", written)]
    )
    assert _angles(spec) == [90, 0]


_BOTH = (
    "A 1000 kg car moving north at 20 m/s and a 1300 kg truck moving west at 16 m/s both "
    "collide at a junction and stick together."
)


def test_a_mass_in_a_sentence_saying_both_is_still_its_own_bodys() -> None:
    right = [_arrow("20 m/s", "north", mass="1000 kg"), _arrow("16 m/s", "west", mass="1300 kg")]
    drawn = _drawn(_BOTH, "bodies", "velocity", right, after="together")
    assert [b.label for b in drawn[0].bodies] == ["1000 kg", "1300 kg"]
    swapped = [{**right[0], "mass": "1300 kg"}, {**right[1], "mass": "1000 kg"}]
    assert _drawn(_BOTH, "bodies", "velocity", swapped, after="together") == []


@pytest.mark.parametrize(
    "question",
    [
        "Find the final velocity when a 1000 kg car moving north at 20 m/s collides with a "
        "1300 kg car moving west at 16 m/s and they stick together. Draw a diagram.",
        "Calculate the velocity after the collision if a 1000 kg car moving north at 20 m/s "
        "hits a 1300 kg car moving west at 16 m/s. Draw a diagram.",
    ],
)
def test_an_asked_after_velocity_leaves_the_stated_ones_before(question: str) -> None:
    cars = [_arrow("20 m/s", "north", mass="1000 kg"), _arrow("16 m/s", "west", mass="1300 kg")]
    (before, *_after) = _drawn(question, "bodies", "velocity", cars)
    assert before.title_key == "before_collision" and _angles(before) == [90, 180]


@pytest.mark.parametrize(
    "question",
    [
        "Car A (1000 kg) and car B (1300 kg) collide at a junction: A was travelling north at "
        "20 m/s and B west at 16 m/s.",
        "Two cars of masses 1000 kg and 1300 kg travel at 20 m/s and 16 m/s due north and due "
        "west respectively.",
    ],
)
def test_a_mass_ties_to_its_body_by_letter_or_in_order(question: str) -> None:
    cars = [_arrow("20 m/s", "north", mass="1000 kg"), _arrow("16 m/s", "west", mass="1300 kg")]
    (spec,) = _drawn(question, "bodies", "velocity", cars)
    assert (spec.bodies[0].label or "").endswith("1000 kg")
    swapped = [{**cars[0], "mass": "1300 kg"}, {**cars[1], "mass": "1000 kg"}]
    assert _drawn(question, "bodies", "velocity", swapped) == []


def test_a_list_of_masses_with_no_order_ties_none() -> None:
    listed = (
        "Two cars of masses 1000 kg and 1300 kg travel at 20 m/s due north and 16 m/s due west."
    )
    cars = [_arrow("20 m/s", "north", mass="1000 kg"), _arrow("16 m/s", "west", mass="1300 kg")]
    assert _drawn(listed, "bodies", "velocity", cars) == []


def test_the_faster_body_heading_the_same_way_is_the_one_behind() -> None:
    chase = "A 1000 kg car at 25 m/s east hits a 3000 kg truck at 10 m/s east from behind."
    cars = [_arrow("25 m/s", "east", mass="1000 kg"), _arrow("10 m/s", "east", mass="3000 kg")]
    (spec,) = _drawn(chase, "bodies", "velocity", cars)
    car, truck = (body.path[0][0] for body in spec.bodies)
    assert car < truck < 0.0


def test_a_label_is_written_from_its_value() -> None:
    push = "A ball moves north with a momentum of 1.2 × 10^4 kg m/s."
    (spec,) = _drawn(push, "tail", "momentum", [_arrow("1.2 × 10^4 kg m/s", "north")])
    assert spec.vectors[0].label is not None and "e" not in spec.vectors[0].label
    assert spec.vectors[0].label.startswith("12000")


def test_a_resultant_against_the_first_arrow_gets_no_half_circle() -> None:
    forces = "Forces of 5 N due east and 8 N due west act on a point."
    (spec,) = _drawn(
        forces, "tail", "force", [_arrow("5 N", "east"), _arrow("8 N", "west")], resultant=True
    )
    assert spec.vectors[-1].label == "R = 3 N" and spec.angles == []


def test_three_points_run_together_are_unread_and_a_dash_joins_two() -> None:
    nne = "A boat sails north-north-east at 20 km/h."
    for way in ("north", "north-east"):
        assert _drawn(nne, "tail", "velocity", [_arrow("20 km/h", way)]) == []
    dash = "A boat sails north–east at 20 km/h."
    assert _drawn(dash, "tail", "velocity", [_arrow("20 km/h", "north")]) == []
    (spec,) = _drawn(dash, "tail", "velocity", [_arrow("20 km/h", "north-east")])
    assert _angles(spec) == [45]


@pytest.mark.parametrize(
    "said",
    [
        "Two roads join at a junction. The cars collide and bounce apart.",
        "The cars collide at the junction and their wheels lock.",
        "The cars collide at the junction. Find their combined mass.",
    ],
)
def test_no_after_picture_unless_the_collision_says_they_stick(said: str) -> None:
    question = (
        "Car A of mass 1000 kg travels at 20 m/s due north and car B of mass 1300 kg travels at "
        f"16 m/s due west. {said}"
    )
    cars = [_arrow("20 m/s", "north", mass="1000 kg"), _arrow("16 m/s", "west", mass="1300 kg")]
    drawn = _drawn(question, "bodies", "velocity", cars, after="together")
    assert [spec.title_key for spec in drawn] == ["before_collision"]


def test_an_angle_in_markup_is_read_as_the_values_are() -> None:
    forces = "Two forces of 6 N and 8 N act at $90^\\circ$ to each other."
    pair = [_arrow("6 N", name="F1"), _arrow("8 N", "90° to F1", name="F2")]
    (spec,) = _drawn(forces, "tail", "force", pair)
    assert _angles(spec) == [0, 90]


_ROUGH = (
    "A 5 kg block on a table with friction is connected over a pulley to a hanging 2 kg mass. "
    "Find the acceleration."
)


def test_a_table_with_friction_is_no_frictionless_rig() -> None:
    from app.modules.physics.extract import extract_physics_intent
    from app.modules.physics.scene_drawing.guards import GUARDS

    intent = extract_physics_intent(_ROUGH)
    assert intent is None or intent.physics_op != "table_pulley"
    assert GUARDS["table_pulley"](Stated.of(_ROUGH), {})
    smooth = _ROUGH.replace("a table with friction", "a frictionless table")
    assert not GUARDS["table_pulley"](Stated.of(smooth), {})
    smooth_intent = extract_physics_intent(smooth)
    assert smooth_intent is not None and smooth_intent.physics_op == "table_pulley"
