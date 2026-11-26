"""Arrows a physics reply describes: each held to a value the question states and to the
direction the question gives that value, laid out and worked out by the server (live,
2026-11-25: two cars meeting at a junction got "I couldn't draw this diagram")."""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from app.modules.physics.scene_drawing.build import physics_fences, scene_fences
from app.modules.physics.scene_drawing.headings import read_heading, stated_headings
from app.modules.physics.scene_drawing.values import Stated
from app.modules.physics.scene_drawing.vectors import described_vectors
from app.modules.physics.schemas import SimulationBlockSpec

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_JUNCTION = (
    "Two roads are perpendicular and meet at a junction. Car A of mass 1000 kg travels "
    "along one road at 20 m/s due North. Car B of mass 1300 kg, travels due West along the "
    "other road at 16 m/s. At the junction the cars collide and move together. a) Write down "
    "the initial velocities of the cars before collision in vector form. b) Find the "
    "velocity of the cars after collision. First draw a diagram of the cars before collision"
)
_CARS = [
    {"name": "Car A", "size": "20 m/s", "direction": "north", "mass": "1000 kg"},
    {"name": "Car B", "size": "16 m/s", "direction": "due west", "mass": "1300 kg"},
]
_HIKER = "A hiker walks 3 km north and then 4 km east. Draw her displacements."
_FORCES = "Two forces of 6 N and 8 N act on a point at right angles to each other. Draw them."
_SWIMMER = (
    "A swimmer swims due north at 1.5 m/s across a river flowing due east at 2 m/s. Draw "
    "the velocity vectors."
)
_HEAD_ON = (
    "A ball of mass 0.2 kg moving at 5 m/s to the right hits a ball of mass 0.3 kg moving "
    "at 2 m/s to the left. Draw the balls before the collision."
)


def _vectors(layout: str, quantity: str, arrows: list[dict[str, str]], **more: Any) -> str:
    return json.dumps(
        {"kind": "vectors", "layout": layout, "quantity": quantity, "arrows": arrows, **more}
    )


def _drawn(body: str, question: str) -> list[SimulationBlockSpec]:
    return described_vectors(body, [question])


def _direction(vector: Any) -> float:
    return math.degrees(math.atan2(vector.dy, vector.dx)) % 360.0


def test_two_cars_meeting_at_a_junction_come_in_along_their_roads() -> None:
    (before,) = _drawn(_vectors("bodies", "velocity", _CARS), _JUNCTION)
    assert before.title_key == "before_collision"
    assert [b.label for b in before.bodies] == ["Car A, 1000 kg", "Car B, 1300 kg"]
    assert [v.label for v in before.vectors] == ["20 m/s", "16 m/s"]
    assert [round(_direction(v)) for v in before.vectors] == [90, 180]
    # Each car sits behind the junction, its arrow toward it: A south of it, B east of it.
    assert before.bodies[0].path[0] == [0.0, -1.0] and before.bodies[1].path[0] == [1.0, 0.0]
    assert before.axes is not None and (before.axes.x_label, before.axes.y_label) == ("E", "N")
    # Arrows keep their sizes in proportion: 20 to 16.
    assert math.hypot(before.vectors[0].dx, before.vectors[0].dy) == pytest.approx(20.0)


def test_cars_that_move_together_after_the_collision_get_the_after_picture() -> None:
    before, after = _drawn(_vectors("bodies", "velocity", _CARS, after="together"), _JUNCTION)
    assert before.title_key == "before_collision" and after.title_key == "after_collision"
    (velocity,) = after.vectors
    # Momentum shared: (1000·20 north + 1300·16 west) / 2300 kg.
    assert velocity.dx == pytest.approx(-20800 / 2300) and velocity.dy == pytest.approx(
        20000 / 2300
    )
    assert velocity.label == "12.55 m/s"
    assert after.angles[0].label == "43.88°"
    assert after.bodies[0].label == "Car A + Car B"


def test_an_after_the_question_does_not_state_is_left_out() -> None:
    """The bodies bounce apart, or the question never says: the before picture only."""
    question = _JUNCTION.replace("collide and move together", "collide")
    drawn = _drawn(_vectors("bodies", "velocity", _CARS, after="together"), question)
    assert [spec.title_key for spec in drawn] == ["before_collision"]


@pytest.mark.parametrize(
    "arrows",
    [
        # The directions swapped: each is the other value's.
        [
            {**_CARS[0], "direction": "west"},
            {**_CARS[1], "direction": "north"},
        ],
        # One car left out: a stated value with a direction is in every picture of it.
        [_CARS[0]],
        # A value the question does not state.
        [_CARS[0], {**_CARS[1], "size": "15 m/s"}],
        # A mass the question does not state.
        [_CARS[0], {**_CARS[1], "mass": "1200 kg"}],
        # A direction no grammar reads.
        [_CARS[0], {**_CARS[1], "direction": "towards the junction"}],
    ],
)
def test_an_arrow_that_does_not_check_draws_nothing(arrows: list[dict[str, str]]) -> None:
    assert _drawn(_vectors("bodies", "velocity", arrows), _JUNCTION) == []


def test_a_name_the_question_does_not_write_goes_unnamed() -> None:
    arrows = [{**_CARS[0], "name": "Red car"}, _CARS[1]]
    (before,) = _drawn(_vectors("bodies", "velocity", arrows), _JUNCTION)
    assert [b.label for b in before.bodies] == ["1000 kg", "Car B, 1300 kg"]


def test_a_walk_in_legs_is_drawn_head_to_tail_with_its_resultant() -> None:
    arrows = [{"size": "3 km", "direction": "north"}, {"size": "4 km", "direction": "east"}]
    (walk,) = _drawn(_vectors("chain", "displacement", arrows, resultant=True), _HIKER)
    assert walk.type == "vector_sum" and walk.title_key == "displacements"
    first, second, result = walk.vectors
    assert second.anchor == [first.dx, first.dy]
    assert result.label == "R = 5 km" and result.role == "result"
    assert [v.stage for v in walk.vectors] == [0, 1, 2]


def test_forces_at_a_right_angle_the_question_states() -> None:
    arrows = [
        {"name": "F1", "size": "6 N"},
        {"name": "F2", "size": "8 N", "direction": "90° to F1"},
    ]
    (forces,) = _drawn(_vectors("tail", "force", arrows, resultant=True), _FORCES)
    assert [round(_direction(v)) for v in forces.vectors[:2]] == [0, 90]
    assert forces.vectors[2].label == "R = 10 N"
    # An angle the question does not state between them draws nothing.
    arrows[1]["direction"] = "60° to F1"
    assert _drawn(_vectors("tail", "force", arrows), _FORCES) == []


def test_two_arrows_with_no_stated_direction_keep_the_angle_between_them() -> None:
    """ "6 N and 8 N at right angles" states no direction: the reply may turn the pair any
    way that keeps the right angle (live corpus, 2026-11-25), and no other angle."""
    arrows = [
        {"name": "6 N force", "size": "6 N", "direction": "up"},
        {"name": "8 N force", "size": "8 N", "direction": "right"},
    ]
    (forces,) = _drawn(_vectors("tail", "force", arrows, resultant=True), _FORCES)
    assert forces.vectors[2].label == "R = 10 N"
    arrows[1]["direction"] = "down"
    assert _drawn(_vectors("tail", "force", arrows), _FORCES) == []
    # A question that states a direction never lets one be chosen.
    assert (
        _drawn(
            _vectors(
                "tail",
                "velocity",
                [{"size": "1.5 m/s", "direction": "up"}, {"size": "2 m/s", "direction": "right"}],
            ),
            _SWIMMER,
        )
        == []
    )


def test_two_directions_in_one_sentence_go_with_their_nearest_values() -> None:
    swimmer = [
        {"name": "swimmer", "size": "1.5 m/s", "direction": "north"},
        {"name": "river", "size": "2 m/s", "direction": "east"},
    ]
    assert _drawn(_vectors("tail", "velocity", swimmer), _SWIMMER)
    swapped = [{**swimmer[0], "direction": "east"}, {**swimmer[1], "direction": "north"}]
    assert _drawn(_vectors("tail", "velocity", swapped), _SWIMMER) == []


def test_a_head_on_pair_faces_each_other_on_a_ground_line() -> None:
    arrows = [
        {"size": "5 m/s", "direction": "right", "mass": "0.2 kg"},
        {"size": "2 m/s", "direction": "to the left", "mass": "0.3 kg"},
    ]
    (before,) = _drawn(_vectors("bodies", "velocity", arrows), _HEAD_ON)
    assert before.ground and before.axes is None
    assert before.bodies[0].path[0][0] < 0 < before.bodies[1].path[0][0]
    # Left and right are sides of the page, never compass points.
    compass = [{**arrows[0], "direction": "east"}, {**arrows[1], "direction": "west"}]
    assert _drawn(_vectors("bodies", "velocity", compass), _HEAD_ON) == []


@pytest.mark.parametrize(
    ("written", "angle"),
    [
        ("due north", 90.0),
        ("south-west", 225.0),
        ("30° east of north", 60.0),
        ("30° north of east", 30.0),
        ("N30°E", 60.0),
        ("S45°W", 225.0),
        ("bearing 060°", 30.0),
        ("30° above the horizontal", 30.0),
        ("left", 180.0),
        ("down", 270.0),
    ],
)
def test_a_description_reads_its_direction(written: str, angle: float) -> None:
    heading = read_heading(written)
    assert heading is not None and not isinstance(heading, str)
    assert getattr(heading, "angle", None) == pytest.approx(angle)


def test_the_question_gives_each_value_its_direction() -> None:
    text = "A drone flies at 12 m/s on a heading 30° east of north, and a wind blows at 5 m/s due east."
    stated = Stated.of(text)
    givens = [given for given in stated.left if given.unit == "m/s"]
    heads = stated_headings(stated.text, givens, [stated.after_at(g) for g in givens])
    assert [[m.angle for m in heads[g.start]] for g in givens] == [[60.0], [0.0]]


def test_vectors_draw_only_when_the_message_asks_to_see_a_picture() -> None:
    body = _vectors("bodies", "velocity", _CARS)
    assert scene_fences([body], [_JUNCTION], asked=False) == []
    (fence,) = physics_fences([body], [_JUNCTION])
    assert fence.startswith("```simulation")


def test_a_table_pulley_scene_is_drawn_from_the_readers_masses() -> None:
    question = (
        "A 4 kg block on a smooth horizontal table is connected by a light string over a "
        "pulley at the edge to a hanging 2 kg mass. Find the acceleration."
    )
    body = json.dumps(
        {"kind": "scene", "scene": "table_pulley", "values": {"mass1": "4 kg", "mass2": "2 kg"}}
    )
    (fence,) = scene_fences([body], [question])
    spec = json.loads(fence.split("\n", 1)[1].rsplit("```", 1)[0])
    assert [b["label"] for b in spec["bodies"]] == ["4 kg", "2 kg"]
    assert spec["pulley"] is not None
    # The masses the other way round are not the reader's block and hanging mass.
    swapped = body.replace('"4 kg"', '"x"').replace('"2 kg"', '"4 kg"').replace('"x"', '"2 kg"')
    assert scene_fences([swapped], [question]) == []
    # A slope is another machine.
    assert scene_fences([body], [question.replace("smooth horizontal table", "30° incline")]) == []
