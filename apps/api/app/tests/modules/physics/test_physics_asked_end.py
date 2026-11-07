"""A question never asks for a value it already states (``law_binding.roles``).

"A car is going 30 m/s after accelerating at 4 m/s² for 5 s. What was its starting
speed?" was verified as 50 m/s: the one speed was read as u and v = u + at answered
"starting speed". Asked for one end of a change (initial, starting, original, at first,
before), the one stated value of that kind is the other end, or the question declines.
Every answer below was worked by hand from the textbook formula.
"""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.ask import asked_end
from app.modules.physics.catalog import CATALOG
from app.services.law_binding.roles import result_role, variable_role
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(math_tools_enabled=True)
_G = 9.81
_WATER_C = 4186.0


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


def _assert_answer(text: str, value: float, unit: str) -> None:
    answer = _answer(text)
    assert answer is not None, f"no verified answer for {text!r}"
    assert math.isclose(answer_number(answer), value, rel_tol=0.01), (text, answer, value)
    assert unit in answer, (text, answer, unit)


# The starting speed of a car that ends at 30 m/s after 4 m/s² for 5 s: u = v - at = 10.
_ENDS = (
    "is going 30 m/s after accelerating at 4 m/s^2 for 5 s",
    "is moving at 30 m/s after accelerating at 4 m/s^2 for 5 s",
    "is travelling at 30 m/s after accelerating at 4 m/s^2 for 5 s",
    "is doing 30 m/s after accelerating at 4 m/s^2 for 5 s",
    "accelerates at 4 m/s^2 for 5 s and ends at 30 m/s",
    "accelerates at 4 m/s^2 for 5 s and finishes at 30 m/s",
    "accelerates at 4 m/s^2 for 5 s and is then going 30 m/s",
    "accelerates at 4 m/s^2 for 5 s and is now doing 30 m/s",
    "accelerates at 4 m/s^2 for 5 s and then has a speed of 30 m/s",
    "accelerates at 4 m/s^2 for 5 s and hits 30 m/s",
    "reaches 30 m/s after accelerating at 4 m/s^2 for 5 s",
)
_ASKS = (
    "What was its starting speed?",
    "What was its initial speed?",
    "Find its initial velocity.",
    "What was its original speed?",
    "What was its speed at first?",
    "How fast was it going at first?",
    "How fast was it going before?",
)


@pytest.mark.parametrize("ends", _ENDS)
@pytest.mark.parametrize("ask", _ASKS)
def test_asked_starting_speed_takes_the_stated_one_as_final(ends: str, ask: str) -> None:
    _assert_answer(f"A car {ends}. {ask}", 10.0, "m/s")


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # "After accelerating ..." opens the sentence: the speed after it is the final one.
        (
            "After accelerating at 4 m/s^2 for 5 s a car is moving at 30 m/s. "
            "Find its initial velocity.",
            10.0,
            "m/s",
        ),
        (
            "A bike accelerates at 2 m/s^2 for 3 s and ends at 12 m/s. What was its starting speed?",
            6.0,
            "m/s",
        ),
        (
            "A truck accelerates at 2 m/s^2 for 6 s and is now doing 20 m/s. What was its initial speed?",
            8.0,
            "m/s",
        ),
        (
            "A cyclist accelerates at 1.5 m/s^2 for 4 s and then has a speed of 11 m/s. "
            "What was her speed at first?",
            5.0,
            "m/s",
        ),
        # A braking car: a = -3 m/s², u = v - at = 8 + 12.
        (
            "A car decelerates at 3 m/s^2 for 4 s and ends at 8 m/s. "
            "How fast was it going before it started braking?",
            20.0,
            "m/s",
        ),
        (
            "A car brakes at 3 m/s^2 for 4 s and is then moving at 8 m/s. What was its initial speed?",
            20.0,
            "m/s",
        ),
        # u = √(v² - 2as) = √(900 - 800).
        (
            "A car accelerates uniformly over 100 m and reaches 30 m/s at 4 m/s^2. "
            "What was its initial speed?",
            10.0,
            "m/s",
        ),
    ],
)
def test_a_starting_speed_is_worked_back_from_the_end(text: str, value: float, unit: str) -> None:
    _assert_answer(text, value, unit)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Asked nothing about an end, the speed stated after the change is still the final
        # one: s = vt - ½at². Read as u, each was 200 m, 45 m and 156 m.
        (
            "A car is going 30 m/s after accelerating at 4 m/s^2 for 5 s. How far did it travel?",
            100.0,
        ),
        (
            "After accelerating at 4 m/s^2 for 5 s a car is moving at 30 m/s. How far did it travel?",
            100.0,
        ),
        ("A bike accelerates at 2 m/s^2 for 3 s and ends at 12 m/s. How far does it go?", 27.0),
        (
            "A truck accelerates at 2 m/s^2 for 6 s and is now doing 20 m/s. How far did it travel?",
            84.0,
        ),
        (
            "A car accelerates at 4 m/s^2 for 5 s and is then going 30 m/s. How far did it go?",
            100.0,
        ),
    ],
)
def test_a_speed_stated_after_the_change_is_the_final_one(text: str, value: float) -> None:
    _assert_answer(text, value, "m")


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # Look-alikes: the stated speed really is the starting one.
        (
            "A car starts at 10 m/s and accelerates at 4 m/s^2 for 5 s. What is its final speed?",
            30.0,
            "m/s",
        ),
        ("A car goes from rest to 30 m/s at 3 m/s^2. How long does it take?", 10.0, "s"),
        (
            "A car is initially moving at 20 m/s and accelerates at 2 m/s^2 for 5 s. "
            "What is its final speed?",
            30.0,
            "m/s",
        ),
        ("A car moving at 20 m/s accelerates at 2 m/s^2 for 5 s. What is its speed?", 30.0, "m/s"),
        (
            "A car travelling at 20 m/s accelerates at 2 m/s^2 for 5 s. How fast is it going?",
            30.0,
            "m/s",
        ),
        (
            "A car moving at 10 m/s accelerates at 4 m/s^2 for 5 s. How far does it travel?",
            100.0,
            "m",
        ),
        (
            "A car moving at 10 m/s then accelerates at 4 m/s^2 for 5 s. How far does it travel?",
            100.0,
            "m",
        ),
        ("A car moving at 30 m/s brakes and stops in 5 s. What was its acceleration?", -6.0, "m/s"),
        (
            "A bus accelerates from rest at 1.5 m/s^2 for 12 s. What is its final speed?",
            18.0,
            "m/s",
        ),
    ],
)
def test_a_stated_starting_speed_is_still_the_start(text: str, value: float, unit: str) -> None:
    _assert_answer(text, value, unit)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # T₁ = T₂ - Q/(mc) and T₂ = T₁ + Q/(mc), water's c = 4186 J/(kg·K).
        (
            "2 kg of water absorbs 336000 J and ends at 80 °C. What was its starting temperature?",
            80 - 336000 / (2 * _WATER_C),
            "°C",
        ),
        (
            "2 kg of water absorbs 336000 J and ends at 80 °C. What was its initial temperature?",
            80 - 336000 / (2 * _WATER_C),
            "°C",
        ),
        (
            "2 kg of water at 20 °C absorbs 336000 J. What is its final temperature?",
            20 + 336000 / (2 * _WATER_C),
            "°C",
        ),
        # Charles: V₁ = V₂T₁/T₂. Read as V₁, the 6 L answered 8 L.
        (
            "A gas is heated at constant pressure from 300 K to 400 K and ends with a volume "
            "of 6 L. What was its initial volume?",
            4.5,
            "L",
        ),
        (
            "A gas is cooled at constant pressure from 400 K to 300 K and ends with a volume "
            "of 3 L. What was its original volume?",
            4.0,
            "L",
        ),
        # Boyle: P₁ = P₂V₂/V₁. Read as P₁, the 300 kPa answered 900 kPa.
        (
            "At constant temperature a gas is compressed from 6 L to 2 L. It ends at 300 kPa. "
            "What was its initial pressure?",
            100.0,
            "kPa",
        ),
        # Gay-Lussac: P₁ = P₂T₁/T₂. Read as P₁, the 200 kPa answered 400 kPa.
        (
            "A gas at constant volume is heated from 300 K to 600 K. Its pressure ends at "
            "200 kPa. What was its initial pressure?",
            100.0,
            "kPa",
        ),
        # Look-alikes asked for the end state.
        (
            "A gas at constant pressure occupies 4 L at 300 K. It is heated to 400 K. "
            "What is its new volume?",
            4 * 400 / 300,
            "L",
        ),
        (
            "At constant temperature a gas at 100 kPa is compressed from 6 L to 2 L. "
            "What is the final pressure?",
            300.0,
            "kPa",
        ),
    ],
)
def test_temperatures_and_gas_states_are_read_at_their_end(
    text: str, value: float, unit: str
) -> None:
    _assert_answer(text, value, unit)


@pytest.mark.parametrize(
    ("text", "wrong"),
    [
        # It states its own answer: 10 m/s is the starting speed.
        (
            "A car starts at 10 m/s and accelerates at 2 m/s^2 for 5 s. What was its initial speed?",
            None,
        ),
        # The impact speed is not the launch speed: read as v₀ it answered 31.9 m/s.
        (
            "A ball is thrown horizontally from a 20 m cliff and hits the ground at 25 m/s. "
            "What was its initial speed?",
            "31.9",
        ),
        (
            "A ball is thrown downward from a 20 m tower and hits the ground at 25 m/s. "
            "What was its initial speed?",
            "31.9",
        ),
        # Reaching the bottom at 6 m/s: read as the speed at the top it answered 7.46 m/s.
        (
            "A 2 kg block slides down a frictionless ramp and reaches the bottom at 6 m/s "
            "after dropping 1 m. What was its initial speed?",
            "7.46",
        ),
        # Two values named for one input ("at" 300 kPa, "initial pressure was" 100 kPa):
        # read as P₂ the 100 kPa answered 0.667 L.
        (
            "A gas at constant temperature is compressed to 2 L at 300 kPa. Its initial "
            "pressure was 100 kPa. What was its initial volume?",
            "0.667",
        ),
        (
            "A gas at constant pressure ends at a volume of 6 L at 400 K. It started at 300 K. "
            "What was its initial volume?",
            "8",
        ),
    ],
)
def test_an_asked_end_never_gets_the_other_ends_answer(text: str, wrong: str | None) -> None:
    answer = _answer(text)
    assert answer is None, (text, answer, wrong)


@pytest.mark.parametrize(
    ("text", "role"),
    [
        ("What was its starting speed?", "initial"),
        ("Find its initial velocity.", "initial"),
        ("What was its original volume?", "initial"),
        ("What was its speed originally?", "initial"),
        ("How fast was it going at first?", "initial"),
        ("How fast was it going before?", "initial"),
        ("How fast was it going before it started braking?", "initial"),
        ("What is the new volume?", "final"),
        ("What is its final temperature?", "final"),
        ("What is its speed?", None),
        ("How fast is it going?", None),
        # "Before it hits the ground" is the end of a fall, not its start.
        ("How fast is it going just before it hits the ground?", None),
        # The role labels a given in the condition, not the asked quantity.
        ("What is the acceleration if the initial speed is 10 m/s?", None),
    ],
)
def test_the_asked_end_is_read_off_the_asked_quantity(text: str, role: str | None) -> None:
    end = asked_end(text)
    assert (None if end is None else end.role) == role


def test_paired_laws_name_their_ends() -> None:
    """The roles come from the catalog's own words, for every family with two ends."""
    expected = {
        "suvat_velocity": "final",
        "suvat_initial_velocity": "initial",
        "boyle_volume": "final",
        "boyle_initial_volume": "initial",
        "charles_initial_temperature": "initial",
        "heat_final_temperature": "final",
        "heat_initial_temperature": "initial",
        "angular_momentum_conservation": "final",
    }
    for operation, role in expected.items():
        assert result_role(CATALOG[operation].binding) == role, operation
    inputs = {
        ("suvat_velocity", "u"): "initial",
        ("suvat_initial_velocity", "v"): "final",
        ("charles_volume", "vol1"): "initial",
        ("charles_initial_volume", "vol2"): "final",
        ("heat_energy", "temp_initial"): "initial",
        ("heat_energy", "temp_final"): "final",
        ("impact_speed", "v0"): "initial",
        ("angular_momentum_conservation", "omega_i"): "initial",
    }
    for (operation, name), role in inputs.items():
        variable = next(v for v in CATALOG[operation].variables if v.name == name)
        assert variable_role(variable) == role, (operation, name)


def test_every_initial_state_gas_law_is_its_forward_law_read_backwards() -> None:
    """P₁V₁ = P₂V₂ read for V₁ from V₂: 6 L at 100 kPa compressed to 300 kPa started at…"""
    for operation, spec in CATALOG.items():
        if "_initial_" not in operation or spec.kind != "thermal" or spec.binding is None:
            continue
        forward = CATALOG.get(operation.replace("_initial_", "_"))
        if forward is None or forward.binding is None:
            continue
        assert spec.binding.result == forward.binding.result
        assert spec.binding.cues == forward.binding.cues
        assert result_role(spec.binding) == "initial"
        assert result_role(forward.binding) == "final"


def test_a_fall_speed_is_still_worked_from_the_launch() -> None:
    """v = √(v₀² + 2gh): thrown down at 5 m/s from 20 m."""
    _assert_answer(
        "A ball is thrown down at 5 m/s from a 20 m tower. How fast does it hit the ground?",
        math.sqrt(25 + 2 * _G * 20),
        "m/s",
    )


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # A speed "from" or "at" which the change happens is its start.
        (
            "After accelerating from 10 m/s at 2 m/s^2 for 5 s, how far has the car travelled?",
            75.0,
            "m",
        ),
        (
            "After braking begins, a car moving at 20 m/s decelerates at 4 m/s^2 for 3 s. "
            "How far does it travel?",
            42.0,
            "m",
        ),
        # "Now" before the change is said is the start.
        (
            "A car is now travelling at 15 m/s. It accelerates at 2 m/s^2 for 4 s. How far does it travel?",
            76.0,
            "m",
        ),
        (
            "A car now has a speed of 10 m/s and accelerates at 2 m/s^2 for 5 s. How far does it travel?",
            75.0,
            "m",
        ),
        # "Before it starts to fall" is the top of the rise: 5 + 20²/2g.
        (
            "A ball is thrown upward at 20 m/s from a 5 m tall cliff. How high above the ground "
            "does it rise before it starts to fall?",
            5 + 400 / (2 * _G),
            "m",
        ),
        # "The final answer" names no end of the speed.
        (
            "A car ends at 30 m/s after accelerating at 4 m/s^2 for 5 s. "
            "What is the final answer for its initial speed?",
            10.0,
            "m/s",
        ),
        (
            "A gas expands from 2 L to 3 L at constant pressure, ending at 450 K. What was its initial temperature?",
            300.0,
            "K",
        ),
        (
            "A gas is cooled from 100 °C to 0 °C at constant pressure and ends with a volume of 2 L. "
            "What was its original volume?",
            2 * 373.15 / 273.15,
            "L",
        ),
    ],
)
def test_a_start_stays_a_start(text: str, value: float, unit: str) -> None:
    _assert_answer(text, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        # Heat taken out of the water, read as a gain, warmed it.
        "2 kg of water at 50 °C transfers 84 kJ of heat to the room. What is its final temperature?",
        "2 kg of water at 50 °C gives up 84 kJ of heat. What is its final temperature?",
        "84 kJ of heat is taken from 2 kg of water at 50 °C. What is its final temperature?",
        "2 kg of water at 50 °C radiates 84 kJ of heat. What is its final temperature?",
        "2 kg of water at 50 °C dissipates 84 kJ of energy. What is its final temperature?",
        "2 kg of water at 10 °C loses 168 kJ of heat. What is its final temperature?",
        # Water that would leave 0-100 °C, ice, a negative Q.
        "2 kg of water at 90 °C absorbs 168 kJ. What is its final temperature?",
        "50 kJ of heat is added to 1 kg of ice at -10 °C. What is its final temperature?",
        "2 kg of water at 5 °C has Q = -84 kJ of heat added. What is its final temperature?",
        "2 kg of water absorbs 336 kJ and ends at 30 °C. What was its initial temperature?",
        # Two asks: both answered, or neither.
        "2 kg of water at 20 °C absorbs 42 kJ. What is the temperature change and the final temperature?",
        # The original pressure stated, not P2.
        "A gas at 2 atm occupies 4 L. It is compressed at constant temperature to 1 L. "
        "What was its original pressure?",
        # d/v never reads the stated acceleration (right: 5 s).
        "A car ends up at 20 m/s after accelerating at 2 m/s^2 over 75 m. How long did it take?",
    ],
)
def test_no_wrong_end_is_verified(text: str) -> None:
    assert _answer(text) is None, (text, _answer(text))
