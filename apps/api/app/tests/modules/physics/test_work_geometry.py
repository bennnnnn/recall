"""A straight-line law of a force's work is never certified for a turn, or for an angle from
another line than the motion; the asked unit is read whole (textbook round, 2026-11-26)."""

from __future__ import annotations

import pytest

from app.modules.physics.ask import asked_unit
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.solver import solve_physics
from app.modules.physics.work_geometry import angle_from_another_line, states_a_turn


@pytest.mark.parametrize(
    "question",
    [
        # W = F s took the 50 cm lever arm as a distance: 135 J for τθ = 424 J.
        "A mechanic tightens a nut and turns it through half a turn. A force of 270 N is "
        "used at a perpendicular distance of 50 cm. How much work is done by the mechanic?",
        # P = W/t took a torque of 100 N m as 100 J: 50 W for τω = 157 W.
        "A mechanic applies a torque of 100 N m over a half turn and takes 2 seconds. "
        "What is the power?",
        # cos 50° for a box raised vertically by a pull at 50° to the horizontal: 72.31 J.
        "A box is attached to a rope, which runs over a pulley above the box. The man pulls "
        "the rope with a force of 75 N at an angle of 50° to the horizontal. The man raises "
        "the box 1.5 m. Use the scalar product to find the work done on the box.",
        "A sled is pulled horizontally 20 m with a force of 40 N at 25° to the vertical. "
        "How much work is done?",
    ],
)
def test_a_straight_line_work_law_is_refused(question: str) -> None:
    assert extract_physics_intent(question) is None


@pytest.mark.parametrize(
    ("question", "value", "unit"),
    [
        (
            "A box is pulled along the floor by a rope at 30° to the horizontal with a force "
            "of 50 N for 10 m. How much work is done?",
            433.013,
            "J",
        ),
        (
            "A motor pulls with a force of 50 N at 2 m/s while its wheel turns at 3 "
            "revolutions per second. What is the power?",
            100.0,
            "W",
        ),
        ("A crane lifts a 200 kg load 10 m in 5 s. What is its power?", 3924.0, "W"),
    ],
)
def test_a_straight_line_work_law_still_answers_its_own(
    question: str, value: float, unit: str
) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None
    result = solve_physics(intent).quantities[0]
    assert result.unit == unit and result.value == pytest.approx(value, rel=1e-4)


@pytest.mark.parametrize(
    ("text", "turns"),
    [
        ("turns it through half a turn", True),
        ("over a half turn", True),
        ("rotates through 3 revolutions", True),
        ("turns through 2.5 rad", True),
        ("spins at 3 revolutions per second", False),
        ("at 20 rad/s", False),
        ("he turns the corner", False),
    ],
)
def test_an_amount_of_turning_is_read(text: str, turns: bool) -> None:
    assert states_a_turn(text) is turns


@pytest.mark.parametrize(
    ("text", "another"),
    [
        ("a pull at 50° to the horizontal raises the box 1.5 m", True),
        ("at 30° to the horizontal along the floor for 10 m", False),
        ("at 25° to the vertical, pulled horizontally 20 m", True),
        ("at 25° to the vertical, lifted 2 m", False),
    ],
)
def test_an_angle_from_another_line_than_the_motion(text: str, another: bool) -> None:
    assert angle_from_another_line(text) is another


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("What speed is he walking at? Give your answer in metres per second.", "m/s"),
        ("What is its speed in km per hour?", "km/h"),
        ("How much energy in kWh?", "kWh"),
        ("What is the speed in m/s?", "m/s"),
    ],
)
def test_the_asked_unit_is_read_whole(text: str, unit: str) -> None:
    assert asked_unit(text) == unit


def test_a_walk_in_feet_answers_in_the_unit_asked() -> None:
    """300 ft/min was carded, verified, for "Give your answer in metres per second"."""
    intent = extract_physics_intent(
        "Berihun walks 3000 feet in 10 minutes. What speed is he walking at? "
        "Give your answer in metres per second."
    )
    assert intent is not None
    result = solve_physics(intent).quantities[0]
    assert result.unit == "m/s" and result.value == pytest.approx(1.524)


@pytest.mark.parametrize(
    "question",
    [
        # The reviewer's input (round 1 of #2604), then the same pull in other words and case.
        "A man pulls the rope with 75 N at 50° above the horizontal and raises the box 1.5 m. "
        "Find the work done on the box.",
        "A box is lifted 1.5 m by a rope pulled with a force of 75 N at 50° to the Horizontal. "
        "How much work is done?",
        "A force of 75 N, applied at an angle of 50 degrees with the ground, hoists a crate "
        "vertically through 1.5 m. Calculate the work done.",
        "Raising the load 1.5 m, the worker pulls with 75 N at an angle of 50° to the "
        "HORIZONTAL. What work does he do?",
        "Pulling with 75 N at 50° below the horizontal, a man lifts a load 1.5 m. Work done?",
        "A rope at 40° to the vertical drags a sled horizontally 20 m with a force of 40 N. "
        "Find the work done.",
    ],
)
def test_an_angle_from_another_line_than_the_motion_is_refused(question: str) -> None:
    assert angle_from_another_line(question)
    assert extract_physics_intent(question) is None


@pytest.mark.parametrize(
    ("question", "value"),
    [
        # The same pulls along the angle's own line: answered by W = Fs cos θ.
        (
            "A man pulls a box along the floor with 75 N at 50° above the horizontal for 1.5 m. "
            "Find the work done.",
            72.31,
        ),
        (
            "A force of 40 N at an angle of 30 degrees with the ground pulls a sled 20 m across "
            "the floor. Work done?",
            692.82,
        ),
    ],
)
def test_an_angle_from_the_motion_s_own_line_is_answered(question: str, value: float) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None
    assert solve_physics(intent).quantities[0].value == pytest.approx(value, rel=1e-3)


@pytest.mark.parametrize(
    "question",
    [
        # The reviewer's input: "each", then a verb no list knew (round 1 of #2604).
        "Two forces of 20 N each act as a couple. The forces act at a distance of 10 cm from "
        "the centre of rotation. What is the torque produced by the couple?",
        "A couple is made of two forces of 20 N each, applied 10 cm from the centre. Find the "
        "torque of the couple.",
        "Two 20 N forces act as a couple, each 10 cm from the pivot. Calculate the torque.",
        "TWO FORCES, EACH OF 20 N, FORM A COUPLE 10 cm FROM THE CENTRE. WHAT IS THE TORQUE?",
        "Each of two forces is 20 N; they form a couple 10 cm either side of the axis. Find the "
        "torque.",
        "Two forces of 20 N each are applied as a couple at 10 cm from the centre of rotation. "
        "Determine the torque.",
    ],
)
def test_a_value_each_of_several_items_is_never_read_once(question: str) -> None:
    """τ = F d read one 20 N force: 2 N·m, checked, for the couple's 4 N·m."""
    intent = extract_physics_intent(question)
    assert intent is None or solve_physics(intent).quantities[0].value == pytest.approx(4.0)


@pytest.mark.parametrize(
    "question",
    [
        "Two charges of 3 µC and -5 µC are 0.2 m apart. Find the force between them.",
        "Two charges of 3 µC and +5 µC are 0.2 m apart. Find the force between them.",
    ],
)
def test_two_values_listed_are_one_each(question: str) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None and intent.physics_op == "electric_force"


@pytest.mark.parametrize(
    "question",
    [
        "A car rounds a turn at 15 m/s with a driving force of 2000 N. What is the power?",
        "A 50-turn coil carries a motor that does 1200 J of work in 60 s. What is the power?",
    ],
)
def test_a_turn_named_as_a_thing_is_no_amount_turned(question: str) -> None:
    assert not states_a_turn(question)
