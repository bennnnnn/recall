"""Questions the physics STEM sweep (``app/tests/behavior/stem_sweep.py``) caught.

The first group were verified and wrong; the second were textbook questions
the solver did not recognise, so the model answered them unchecked.
"""

from __future__ import annotations

import re

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.direct import maybe_direct_physics_reply
from app.modules.web_search.geo_intent import is_distance_query
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


def _block(text: str) -> VerifiedPhysicsBlock | None:
    intent = extract_physics_intent(text)
    return None if intent is None else build_verified_physics_block(intent, _SETTINGS)


def _values(text: str) -> list[tuple[float, str]]:
    """Each value and unit of the plain verified answer: "2.8 m/s² and 14 N"."""
    answer = _answer(text)
    assert answer is not None, f"no verified answer for {text!r}"
    found: list[tuple[float, str]] = []
    for part in re.split(r" and |; ", answer):
        part = re.sub(r"^[^\d-]*=\s*", "", part)  # "v = 20 m/s"
        number = answer_number(part)
        unit = re.sub(r"^-?[\d.]+(?: × 10[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)?\s*", "", part).split(" (")[0]
        found.append((number, unit.strip()))
    return found


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


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        (
            # Two legs: the whole distance over the whole time, not the mean speed (75).
            "A car travels at a constant speed of 50 km/h for 100 km. It then speeds up to "
            "100 km/h and is driven another 100 km. What is the car's average speed for the "
            "200 km trip?",
            "66.7 km/h",
        ),
        (
            "A car drives at 60 km/h for 120 km and then at 80 km/h for another 120 km. "
            "What is its average speed for the 240 km trip?",
            "68.6 km/h",
        ),
        (
            # The legs pair in the order written: 2 h, then 3 h.
            "A car travels 100 km at 50 km/h and then 300 km at 100 km/h. "
            "What is its average speed?",
            "80 km/h",
        ),
        (
            # The same distance each way: the harmonic mean, not 25.
            "A cyclist rides to town at 20 km/h and returns at 30 km/h. "
            "What is her average speed for the round trip?",
            "24 km/h",
        ),
        (
            # The same time at each speed: the plain mean.
            "A car travels at 40 km/h for half the time and 60 km/h for the other half. "
            "What is its average speed?",
            "50 km/h",
        ),
        (
            # Mixed units are worked in m, s and m/s.
            "A runner covers 3 km at 2 m/s and then 1 km at 4 m/s. What is her average speed?",
            "2.29 m/s",
        ),
        (
            # "Average velocity" and a clause before the question.
            "A passenger walks 4 m forward in 8 s to take his seat on provided place forward. "
            "What is his average velocity?",
            "0.5 m/s",
        ),
    ],
)
def test_average_speed_over_a_trip_is_verified(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # The legs make 240 km; the question says 250.
        "A car drives at 60 km/h for 120 km and then at 80 km/h for another 120 km. "
        "What is its average speed for the 250 km trip?",
        # Two vehicles' speeds, not one trip: no average speed law fits.
        "A car's speed is 60 km/h and a bus's speed is 40 km/h. What is their average speed?",
    ],
)
def test_an_average_speed_question_without_one_answer_is_not_verified(text: str) -> None:
    assert _answer(text) is None


# --- Round 5: wrong verified answers the STEM investigation found ------------------
#
# Every expected value below was worked by hand (g = 9.81 m/s²). Each was verified and
# wrong before; now it is right, or it is left to the model unverified.

_ROUND5_RIGHT: list[tuple[str, float, str]] = [
    # 1. "Thrown straight down" and "throws a ball down" point down, not up.
    (
        "A ball is thrown straight down at 8 m/s from the top of a 40 m building. "
        "how long does it take to hit the ground?",
        2.154,
        "s",
    ),
    (
        "someone throws a ball down at 6 m/s from a 20 m balcony, time to hit the ground?",
        1.498,
        "s",
    ),
    (
        "a ball is thrown straight down at 10 m/s from a 50 m cliff. how long to reach the ground",
        2.332,
        "s",
    ),
    (
        "A ball is thrown straight down at 8 m/s from the top of a 40 m building. "
        "what is its height after 1 s?",
        27.1,
        "m",
    ),
    (
        "a rock is thrown vertically down at 12 m/s from a 60 m bridge. "
        "how long till it hits the water?",
        2.482,
        "s",
    ),
    # The control: straight up still points up.
    (
        "A ball is thrown straight up at 8 m/s from the top of a 40 m building. "
        "how long does it take to hit the ground?",
        3.785,
        "s",
    ),
    # 2. Below the horizontal is a negative launch angle.
    (
        "A ball is thrown at 10 m/s at 30° below the horizontal from the top of a 20 m "
        "building. how far from the base does it land?",
        13.62,
        "m",
    ),
    # 3. Straight up and back to the hand needs no height.
    ("A ball is thrown straight up at 20 m/s. How long is it in the air?", 4.077, "s"),
    # 20. The asked unit is the answer's unit.
    ("What is the gauge pressure in psi at a depth of 10 m in fresh water?", 14.23, "psi"),
]


@pytest.mark.parametrize(("text", "value", "unit"), _ROUND5_RIGHT)
def test_a_round5_wrong_answer_is_now_right(text: str, value: float, unit: str) -> None:
    values = _values(text)
    assert any(
        found_unit == unit and found == pytest.approx(value, rel=0.01)
        for found, found_unit in values
    ), values


_ROUND5_DECLINED = [
    # 2. A downward launch peaks where it starts: not the upward formula.
    "A ball is thrown at 10 m/s at 30° below the horizontal from a 20 m cliff. "
    "what is its maximum height?",
    # 3. No height: there is no fall time to give, and h₀ = 0 is not stated.
    "A rock is thrown horizontally off a cliff at 12 m/s. how long until it lands?",
    "A ball is thrown horizontally at 15 m/s. how long until it hits the ground?",
    "A ball rolls off a table at 3 m/s. how long until it hits the floor?",
    "A stone is thrown horizontally from a cliff at 20 m/s. what's its speed when it lands?",
    "A ball is kicked horizontally off a roof at 8 m/s. how far from the building does it land?",
    "a stone is thrown down a well at 4 m/s, how deep is the well?",
    "A ball is thrown at 25 m/s. How long is it in the air?",
    # 16. A statement with no question asks nothing.
    "A ball is dropped from 80 m.",
]


@pytest.mark.parametrize("text", _ROUND5_DECLINED)
def test_a_round5_wrong_answer_is_now_declined(text: str) -> None:
    assert _answer(text) is None


def test_an_upward_throw_with_no_height_invents_no_zero_in_its_working() -> None:
    block = _block("A ball is thrown straight up at 20 m/s. How long is it in the air?")
    assert block is not None
    for row in block.physics_formulas:
        assert "h_0" not in row, row
    for row in block.physics_substitutions:
        assert re.search(r"(?<![\d._{])0(?![\d.}])", row) is None, row


@pytest.mark.parametrize(
    ("text", "value", "unit", "verdict"),
    [
        (
            # 16. A student's result is never a given: the impact speed is checked.
            "A 2 kg ball is dropped from 20 m. I got 19.8 m/s for its impact speed. Am I right?",
            19.8,
            "m/s",
            "right",
        ),
        (
            "A ball is dropped from 20 m. I calculated 2.02 s to hit the ground. Is that right?",
            2.02,
            "s",
            "right",
        ),
        (
            "A ball is thrown at 20 m/s at 30 degrees. I got a range of 20.4 m. Is that right?",
            35.3,
            "m",
            "wrong",
        ),
        (
            "A 12 V battery drives current through a 4 ohm resistor. I got 48 A. Is that right?",
            3.0,
            "A",
            "wrong",
        ),
    ],
)
def test_a_claimed_result_is_checked_not_used_as_a_given(
    text: str, value: float, unit: str, verdict: str
) -> None:
    values = _values(text)
    assert values[0][0] == pytest.approx(value, rel=0.01)
    assert values[0][1] == unit
    block = _block(text)
    assert block is not None
    reply = maybe_direct_physics_reply(block, text)
    assert reply is not None
    head = reply.split("**Given**")[0]
    if verdict == "right":
        assert "is right" in head, head
    else:
        assert "is right" not in head and "not" in head, head
    given = reply.split("**Given**")[1].split("**Find**")[0]
    assert "19.8" not in given and "20.4" not in given and "48" not in given


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # A yes/no about a value asks for that value, never a time.
        ("A ball is dropped from 20 m. Does it hit the ground at 19.8 m/s?", 19.8, "m/s"),
        (
            "A ball is dropped from 20 m. My friend says it hits at 19.8 m/s. "
            "How fast does it actually hit?",
            19.8,
            "m/s",
        ),
    ],
)
def test_a_claim_in_a_question_is_never_a_given(text: str, value: float, unit: str) -> None:
    values = _values(text)
    assert values[0][0] == pytest.approx(value, rel=0.01)
    assert values[0][1] == unit


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # 17. A planet in a side question does not replace Earth in the main one.
        (
            "A ball is dropped from 20 m. How fast does it hit the ground? "
            "Would it be different on Mars?",
            19.81,
            "m/s",
        ),
        (
            "A ball is thrown at 20 m/s at 30 degrees from a 10 m cliff. How far from the base "
            "does it land? Ignore air resistance, and also tell me how this changes on the Moon.",
            48.04,
            "m",
        ),
        ("How long does a ball take to fall 20 m on Earth? Compare with Jupiter.", 2.019, "s"),
    ],
)
def test_a_body_in_a_side_question_keeps_the_main_question_on_earth(
    text: str, value: float, unit: str
) -> None:
    values = _values(text)
    assert values[0][0] == pytest.approx(value, rel=0.01)
    assert values[0][1] == unit
    block = _block(text)
    assert block is not None
    # The side question is the model's to answer, beside the verified main one.
    assert maybe_direct_physics_reply(block, text) is None


def test_a_body_in_the_main_question_still_sets_its_gravity() -> None:
    values = _values("A ball is dropped from 20 m on Mars. How fast does it hit the ground?")
    assert values[0][0] == pytest.approx((2 * 3.71 * 20) ** 0.5, rel=0.01)


@pytest.mark.parametrize(
    "text",
    [
        # 18. A question in parts is never answered one part at a time.
        "A ball is dropped from 45 m. (a) how long does it take to hit the ground? "
        "(b) how fast is it going when it lands?",
        "A 1500 kg car at 20 m/s brakes to a stop in 5 s. "
        "Find the deceleration and the braking force.",
        "a ball is thrown straight up at 20 m/s. (a) max height (b) time to reach the top "
        "(c) total time in the air",
        # A yes/no question about a value is the model's to answer, with the check.
        "A ball is dropped from 20 m. Does it hit the ground at 19.8 m/s?",
    ],
)
def test_a_question_with_parts_left_unanswered_gets_no_instant_reply(text: str) -> None:
    block = _block(text)
    if block is not None:
        assert maybe_direct_physics_reply(block, text) is None


def test_every_part_of_a_suvat_question_is_answered_in_one_reply() -> None:
    text = (
        "A car accelerates uniformly from rest at 2 m/s^2 for 10 s. "
        "Find (a) its final speed and (b) the distance travelled."
    )
    values = _values(text)
    assert values[0][0] == pytest.approx(20.0) and values[0][1] == "m/s"
    assert values[1][0] == pytest.approx(100.0) and values[1][1] == "m"
    block = _block(text)
    assert block is not None
    assert maybe_direct_physics_reply(block, text) is not None


def test_a_statement_with_no_question_gets_no_instant_reply() -> None:
    text = "a 2 kg ball at 3 m/s collides elastically with a 1 kg ball at rest"
    block = _block(text)
    assert block is not None
    assert maybe_direct_physics_reply(block, text) is None
