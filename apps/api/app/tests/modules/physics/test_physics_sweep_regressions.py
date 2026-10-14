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


@pytest.mark.parametrize(
    ("text", "op", "answer"),
    [
        ("How long does light take to cross 3000 km?", "light_travel_time", "0.01 s"),
        (
            "What is the gravitational force between Earth and a 1 kg mass at its surface?",
            "gravitational_force_at_surface",
            "9.82 N",
        ),
        ("Find the force between two 1 µC charges 5 cm apart.", "electric_force", "3.6 N"),
        (
            "Two identical 4 nC charges are 2 cm apart. What is the force between them?",
            "electric_force",
            "3.6 × 10⁻⁴ N",
        ),
        (
            "A 10 kg box is pulled with 50 N to the right and 20 N to the left. "
            "What is its acceleration?",
            "acceleration_from_opposing_forces",
            "3 m/s²",
        ),
        (
            "A 50 g bullet is fired from a 4 kg rifle at 400 m/s. "
            "What is the recoil speed of the rifle?",
            "recoil_speed",
            "5 m/s",
        ),
        (
            "An ice skater of 60 kg pushes off another skater of 40 kg. "
            "If the first moves away at 2 m/s, how fast does the second move?",
            "push_off_speed",
            "3 m/s",
        ),
        (
            "A 50 kg girl and a 70 kg boy push off each other on ice. "
            "If the second moves at 1 m/s, how fast does the first move?",
            "push_off_speed_first",
            "1.4 m/s",
        ),
        (
            "A water wave travels 12 m in 4 s and its wavelength is 1.5 m. What is the frequency?",
            "wave_frequency_from_travel",
            "2 Hz",
        ),
        (
            "A sound is 60 dB. A second sound is 100 times more intense. What is its level?",
            "sound_level_from_ratio",
            "80 dB",
        ),
        (
            "A 100 W TV is left on for 5 hours a day for 30 days. "
            "Electricity costs $0.15 per kWh. How much energy does it use?",
            "energy_over_days",
            "5.4 × 10⁷ J (15 kWh)",
        ),
    ],
)
def test_a_question_the_model_used_to_answer_alone_is_verified(
    text: str, op: str, answer: str
) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_op == op
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # A price is never a law's input, and the cost is not an energy.
        "A 2 kW heater runs for 3 hours. Electricity costs $0.20 per kWh. "
        "How much does it cost to run?",
        # Both pull the same way: not a difference.
        "A 5 kg box is pulled with 30 N to the right and 10 N to the right. "
        "What is its acceleration?",
        # Sound is not light.
        "How long does sound take to travel 3000 m?",
        # The ratio is a quieter sound; the law as written is a louder one.
        "A sound is 90 dB. Another is 1000 times less intense. What is its level?",
    ],
)
def test_a_look_alike_of_a_new_law_is_not_answered_by_it(text: str) -> None:
    assert _answer(text) is None


def test_a_price_beside_a_motion_question_is_ignored() -> None:
    assert (
        _answer("A ticket costs $12 and the train travels at 30 m/s for 600 s. How far does it go?")
        == "18000 m"
    )


def test_an_energy_from_watts_and_hours_also_reads_in_kilowatt_hours() -> None:
    assert (
        _answer("what is the energy used by a 2000 W heater in 3 hours") == "2.16 × 10⁷ J (6 kWh)"
    )
    # Seconds are a physics class's unit: no kWh beside them.
    assert _answer("A 60 W bulb is on for 30 s. How much energy does it use?") == "1800 J"
