"""Arrows a physics reply describes, held to the question in the cases review round 1 of
#2593 found: a wind named for where it comes from, each body's own mass and name, momenta
that cancel, small pictures, values after a collision, bare sides, lead words, hard wraps,
"respectively", equal values, shared masses, units, five legs, and the table pulley."""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from app.modules.physics.scene_drawing.values import Stated
from app.modules.physics.scene_drawing.vectors import described_vectors
from app.modules.physics.schemas import SimulationBlockSpec

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_JUNCTION = (
    "Two roads are perpendicular and meet at a junction. Car A of mass 1000 kg travels "
    "along one road at 20 m/s due North. Car B of mass 1300 kg, travels due West along the "
    "other road at 16 m/s. At the junction the cars collide and move together. Draw the cars."
)
_CARS = [
    {"name": "Car A", "size": "20 m/s", "direction": "north", "mass": "1000 kg"},
    {"name": "Car B", "size": "16 m/s", "direction": "west", "mass": "1300 kg"},
]
_WEST_WIND = (
    "A plane flies due north at 200 km/h. The wind blows from the west at 50 km/h. Draw the "
    "velocity vectors."
)


def _vectors(layout: str, quantity: str, arrows: list[dict[str, str]], **more: Any) -> str:
    return json.dumps(
        {"kind": "vectors", "layout": layout, "quantity": quantity, "arrows": arrows, **more}
    )


def _drawn(body: str, question: str) -> list[SimulationBlockSpec]:
    return described_vectors(body, [question])


def _angles(question: str, layout: str, quantity: str, arrows: list[dict[str, str]]) -> list[int]:
    (spec, *_rest) = _drawn(_vectors(layout, quantity, arrows), question)
    return [round(math.degrees(math.atan2(v.dy, v.dx)) % 360.0) for v in spec.vectors]


@pytest.mark.parametrize(
    ("question", "others", "value", "points", "named_from"),
    [
        (_WEST_WIND, [("200 km/h", "north")], "50 km/h", "east", "west"),
        (
            "A boat sails due east at 5 m/s in a north wind of 3 m/s. Draw the velocities.",
            [("5 m/s", "east")],
            "3 m/s",
            "south",
            "north",
        ),
        (
            "A kite is held in a north-easterly wind of 8 m/s. Draw the wind.",
            [],
            "8 m/s",
            "south-west",
            "north-east",
        ),
        (
            "The current flows from the south at 3 m/s. Draw its velocity.",
            [],
            "3 m/s",
            "north",
            "south",
        ),
    ],
)
def test_a_wind_or_current_points_away_from_where_it_comes_from(
    question: str, others: list[tuple[str, str]], value: str, points: str, named_from: str
) -> None:
    """A wind is named for where it comes from: a west wind blows east (review, high)."""
    arrows = [{"size": size, "direction": way} for size, way in others]
    assert _drawn(
        _vectors("tail", "velocity", [*arrows, {"size": value, "direction": points}]), question
    )
    backwards = {"size": value, "direction": named_from}
    assert _drawn(_vectors("tail", "velocity", [*arrows, backwards]), question) == []


def test_a_wind_described_as_the_question_words_it_points_the_right_way() -> None:
    arrows = [
        {"size": "200 km/h", "direction": "north"},
        {"size": "50 km/h", "direction": "from the west"},
    ]
    assert _angles(_WEST_WIND, "tail", "velocity", arrows) == [90, 0]


def test_each_mass_and_name_is_its_own_bodys() -> None:
    """Car A's 1000 kg is no mass of Car B's: swapped masses draw nothing, and a name the
    question gives the other car is left off."""
    swapped = [{**_CARS[0], "mass": "1300 kg"}, {**_CARS[1], "mass": "1000 kg"}]
    assert _drawn(_vectors("bodies", "velocity", swapped, after="together"), _JUNCTION) == []
    renamed = [{**_CARS[0], "name": "Car B"}, {**_CARS[1], "name": "Car A"}]
    (before,) = _drawn(_vectors("bodies", "velocity", renamed), _JUNCTION)
    assert [b.label for b in before.bodies] == ["1000 kg", "1300 kg"]


@pytest.mark.parametrize(
    ("masses", "speeds"),
    [(("2 kg", "3 kg"), ("3 m/s", "2 m/s")), (("0.1 kg", "0.3 kg"), ("3 m/s", "1 m/s"))],
)
def test_momenta_that_cancel_leave_the_before_picture_alone(
    masses: tuple[str, str], speeds: tuple[str, str]
) -> None:
    """At rest after sticking: no arrow of a float's 1e-16 m/s, and the before stays."""
    question = (
        f"A {masses[0]} ball moving at {speeds[0]} to the right hits a {masses[1]} ball moving "
        f"at {speeds[1]} to the left. They stick together. Draw the balls."
    )
    arrows = [
        {"size": speeds[0], "direction": "right", "mass": masses[0]},
        {"size": speeds[1], "direction": "left", "mass": masses[1]},
    ]
    drawn = _drawn(_vectors("bodies", "velocity", arrows, after="together"), question)
    assert [spec.title_key for spec in drawn] == ["before_collision"]


@pytest.mark.parametrize(
    ("question", "quantity", "arrows"),
    [
        (
            "Forces of 0.2 N due east and 0.3 N due north act on a point. Draw them.",
            "force",
            [("0.2 N", "east"), ("0.3 N", "north")],
        ),
        (
            "An ant walks 3 cm north and then 4 cm east. Draw its walk.",
            "displacement",
            [("3 cm", "north"), ("4 cm", "east")],
        ),
    ],
)
def test_a_small_picture_keeps_its_axes_through_the_start(
    question: str, quantity: str, arrows: list[tuple[str, str]]
) -> None:
    described = [{"size": size, "direction": way} for size, way in arrows]
    (spec,) = _drawn(_vectors("tail", quantity, described, resultant=True), question)
    assert spec.axes is not None
    assert spec.axes.x[0] <= 0.0 <= spec.axes.x[1] and spec.axes.y[0] <= 0.0 <= spec.axes.y[1]


_AFTER_STATED = (
    "A 0.2 kg ball moving at 5 m/s to the right hits a 0.3 kg ball at rest. After the "
    "collision the first ball moves at 1 m/s to the left. Draw the balls before the collision."
)


def test_a_before_picture_leaves_out_what_happens_after() -> None:
    before = [{"size": "5 m/s", "direction": "right", "mass": "0.2 kg"}]
    assert _drawn(_vectors("bodies", "velocity", before), _AFTER_STATED)
    late = [*before, {"size": "1 m/s", "direction": "left", "mass": "0.3 kg"}]
    assert _drawn(_vectors("bodies", "velocity", late), _AFTER_STATED) == []


_BARE_SIDES = "A ball moving left at 3 m/s hits a ball moving right at 2 m/s. Draw the balls."


def test_a_bare_side_after_a_motion_verb_is_its_direction() -> None:
    arrows = [{"size": "3 m/s", "direction": "left"}, {"size": "2 m/s", "direction": "right"}]
    assert _angles(_BARE_SIDES, "bodies", "velocity", arrows) == [180, 0]
    # No default to the right against the left the question gives.
    unset = [{"size": "3 m/s"}, arrows[1]]
    assert _drawn(_vectors("bodies", "velocity", unset), _BARE_SIDES) == []


@pytest.mark.parametrize("written", ["to the north", "towards the north", "heading north"])
def test_a_description_may_copy_the_questions_lead_words(written: str) -> None:
    question = "Car A moves at 20 m/s to the north and Car B moves at 15 m/s towards the east."
    arrows = [{"size": "20 m/s", "direction": written}, {"size": "15 m/s", "direction": "east"}]
    assert _angles(question, "bodies", "velocity", arrows) == [90, 0]


def test_a_hard_wrapped_line_and_respectively_keep_their_directions() -> None:
    arrows = [{"size": "20 m/s", "direction": "north"}, {"size": "16 m/s", "direction": "west"}]
    wrapped = (
        "Car A travels at 20 m/s due North. Car B travels due West along the\nother road at 16 m/s."
    )
    assert _angles(wrapped, "bodies", "velocity", arrows) == [90, 180]
    paired = "Two cars travel at 20 m/s and 16 m/s due north and due west respectively."
    assert _angles(paired, "bodies", "velocity", arrows) == [90, 180]
    swapped = [{**arrows[0], "direction": "west"}, {**arrows[1], "direction": "north"}]
    assert _drawn(_vectors("bodies", "velocity", swapped), paired) == []


def test_equal_values_go_to_the_arrow_whose_direction_agrees() -> None:
    equal = "Car A travels north at 20 m/s. Car B travels west at 20 m/s."
    arrows = [{"size": "20 m/s", "direction": "west"}, {"size": "20 m/s", "direction": "north"}]
    assert _angles(equal, "bodies", "velocity", arrows) == [180, 90]


def test_a_mass_stated_for_each_body_serves_each() -> None:
    shared = (
        "Two identical trolleys, each of mass 2 kg, move towards each other at 3 m/s to the "
        "right and 1 m/s to the left."
    )
    trolleys = [
        {"size": "3 m/s", "direction": "right", "mass": "2 kg"},
        {"size": "1 m/s", "direction": "left", "mass": "2 kg"},
    ]
    (spec,) = _drawn(_vectors("bodies", "velocity", trolleys), shared)
    assert [b.label for b in spec.bodies] == ["2 kg", "2 kg"]


def test_the_after_velocity_is_in_the_unit_the_question_states() -> None:
    question = (
        "Car A of mass 1000 kg travels at 72 km/h due north and car B of mass 1500 kg travels "
        "at 54 km/h due west. They collide and stick together. Draw the cars."
    )
    arrows = [
        {"size": "72 km/h", "direction": "north", "mass": "1000 kg"},
        {"size": "54 km/h", "direction": "west", "mass": "1500 kg"},
    ]
    _before, after = _drawn(_vectors("bodies", "velocity", arrows, after="together"), question)
    # (1000·20 north + 1500·15 west) / 2500 kg = 12.04 m/s = 43.35 km/h.
    assert after.vectors[0].label == "43.35 km/h"


def test_a_walk_of_five_legs_is_drawn_in_six_stages() -> None:
    question = (
        "A walker goes 1 km north, then 2 km east, then 3 km south, then 4 km west, then 5 km "
        "north. Draw the walk and its resultant."
    )
    legs = [("1 km", "north"), ("2 km", "east"), ("3 km", "south"), ("4 km", "west")]
    arrows = [{"size": size, "direction": way} for size, way in [*legs, ("5 km", "north")]]
    (walk,) = _drawn(_vectors("chain", "displacement", arrows, resultant=True), question)
    assert [v.stage for v in walk.vectors] == [0, 1, 2, 3, 4, 5]
    assert walk.vectors[-1].label == "R = 3.61 km"


def test_the_table_pulley_guard_refuses_a_slope_and_a_massive_pulley() -> None:
    from app.modules.physics.scene_drawing.guards import GUARDS

    guard = GUARDS["table_pulley"]
    level = (
        "A 4 kg block on a smooth horizontal plane is pulled over a pulley by a hanging 2 kg mass."
    )
    assert not guard(Stated.of(level), {})
    assert guard(Stated.of(level.replace("smooth horizontal plane", "smooth ramp")), {})
    assert guard(Stated.of(level.replace("a pulley", "a pulley of radius 0.1 m")), {})


def test_the_table_pulley_solve_draws_its_rig() -> None:
    from app.modules.physics.extract import extract_physics_intent
    from app.modules.physics.solver import solve_physics

    intent = extract_physics_intent(
        "A 4 kg block on a smooth horizontal table is connected by a light string over a "
        "pulley at the edge to a hanging 2 kg mass. Find the acceleration."
    )
    assert intent is not None and intent.physics_op == "table_pulley"
    (scene,) = solve_physics(intent).simulation_specs
    assert scene.pulley is not None and [b.label for b in scene.bodies] == ["4 kg", "2 kg"]
