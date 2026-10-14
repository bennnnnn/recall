"""Questions the physics STEM sweep (``app/tests/behavior/stem_sweep.py``) caught.

The first group were verified and wrong; the second were textbook questions
the solver did not recognise, so the model answered them unchecked.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.web_search.geo_intent import is_distance_query

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("text", "was", "now"),
    [
        (
            # "How long" asked for a length, not a time.
            "A plane needs 60 m/s to take off and accelerates at 3 m/s^2 from rest. "
            "How long must the runway be?",
            "20 s",
            "600 m",
        ),
        (
            # The top of the throw, not the whole flight.
            "A ball is thrown straight up at 12 m/s. How long until it reaches the top?",
            "2.45 s",
            "1.22 s",
        ),
        (
            "A ball is thrown straight up at 15 m/s. Find the time to reach the top.",
            "3.06 s",
            "1.53 s",
        ),
        (
            # A level launch: the fall sets the time, not d/v.
            "A ball rolls off a 1.2 m high table with a speed of 3 m/s. "
            "How long does it take to hit the floor?",
            "0.4 s",
            "0.495 s",
        ),
        (
            # The sound goes there and back.
            "An echo returns 0.6 s after a shout toward a cliff. "
            "If sound travels at 340 m/s, how far is the cliff?",
            "204 m",
            "102 m",
        ),
        (
            # The car's weight is on the large piston.
            "A hydraulic lift has a small piston of area 0.01 m^2 and a large piston "
            "of area 0.5 m^2. What force on the small piston lifts a 10000 N car?",
            "500000 N",
            "200 N",
        ),
    ],
)
def test_a_wrong_answer_the_sweep_found_is_right(text: str, was: str, now: str) -> None:
    assert _answer(text) == now != was


@pytest.mark.parametrize(
    ("text", "op", "answer"),
    [
        (
            "A car travels at 54 km/h. How many metres does it cover in 10 s?",
            "rate_distance",
            "150 m",
        ),
        (
            "A diver steps off a 10 m platform. With what speed does she hit the water?",
            "drop_speed",
            "14 m/s",
        ),
        (
            "A 60 kg skydiver falls at constant (terminal) velocity. "
            "What is the air resistance on her?",
            "terminal_drag",
            "589 N",
        ),
        (
            "what is the component of gravity along a 40 degree slope for a 3 kg mass",
            "weight_along_slope",
            "18.9 N",
        ),
        (
            "A 0.2 kg ball's velocity changes from 0 to 25 m/s in 0.01 s when kicked. "
            "What is the average force?",
            "average_force_from_speeds",
            "500 N",
        ),
        (
            "A 1200 kg car slows from 20 m/s to rest in 4 s. What is the average braking force?",
            "average_force_from_speeds",
            "6000 N (opposing the motion)",
        ),
        (
            "A 0.5 kg ball on a string is swung in a circle of radius 1.2 m at 6 m/s. "
            "What is the tension (ignore gravity)?",
            "circle_string_tension",
            "15 N",
        ),
        ("What is the acceleration due to gravity on Mars?", "surface_gravity_named", "3.73 m/s²"),
        ("How long should a pendulum be to have a period of 2 s?", "pendulum_length", "0.994 m"),
        ("A 60 W bulb runs on 120 V. What current does it draw?", "current_from_power", "0.5 A"),
        (
            "A 3 kg block of aluminium (c = 900 J/kg·K) absorbs 54 kJ. "
            "What is its temperature rise?",
            "temperature_change_from_heat",
            "20 K",
        ),
        (
            "How much energy is released if 1 g of mass is converted completely to energy?",
            "mass_energy_equivalence",
            "8.99 × 10¹³ J",
        ),
        (
            "A 0.002 m^3 stone is fully submerged in water. What is the upthrust?",
            "upthrust",
            "19.6 N",
        ),
        (
            "What is the critical angle for glass of refractive index 1.5?",
            "critical_angle",
            "41.8°",
        ),
    ],
)
def test_a_textbook_question_the_sweep_found_is_solved(text: str, op: str, answer: str) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_op == op
    assert _answer(text) == answer


def test_a_floating_body_is_not_read_as_fully_submerged() -> None:
    # A floating body displaces less than its own volume.
    assert _answer("what is the upthrust on a 0.002 m^3 object floating in water") is None


@pytest.mark.parametrize(
    "text",
    [
        "A 5 kg block rests on a 30 degree incline. What is the normal force?",
        "A 4 kg block is held at rest on a 30 degree incline by friction. "
        "What is the friction force?",
    ],
)
def test_a_resting_block_does_not_invent_a_friction_coefficient(text: str) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None
    assert "mu" not in intent.physics_params


@pytest.mark.parametrize(
    "text",
    [
        "An object is 30 cm from a lens of focal length 10 cm. How far is the image from the lens?",
        "An echo returns 0.6 s after a shout toward a cliff. "
        "If sound travels at 340 m/s, how far is the cliff?",
        "A candle stands 20 cm in front of a concave mirror with focal length 15 cm. "
        "How far away is the image?",
    ],
)
def test_a_how_far_physics_question_is_not_a_location_lookup(text: str) -> None:
    assert not is_distance_query(text)


def test_a_how_far_place_question_is_still_a_location_lookup() -> None:
    assert is_distance_query("How far is the closest eyeglasses store from me?")
