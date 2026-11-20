"""A result keeps the sign its own definition gives, with its word; a sign an axis gives
stays a size with a direction (owner, 2026-11-20; ``Binding.keeps_sign``)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # Q = mcΔT with ΔT = final - initial: heat given out is negative, "released".
        (
            "A 200 g of copper is cooled from 100 °C to 0 °C. How much heat is given off? "
            "(c = 385 J/kg °C)",
            "-7700 J (released)",
        ),
        (
            "The temperature of 3 kg of water decreases by 10 °C. c = 4200 J/kg°C. How much "
            "heat is released?",
            "-1.26 × 10⁵ J (released)",
        ),
        (
            "A 2 kg block of iron (c = 450 J/kg°C) cools by 20 °C. How much heat does it give out?",
            "-18000 J (released)",
        ),
        # Heat taken in stays positive, a rise unsigned.
        (
            "A 2 kg block (c = 450 J/kg°C) is heated by 20 °C. How much heat does it take in?",
            "18000 J",
        ),
    ],
)
def test_heat_given_out_keeps_its_minus_sign(text: str, answer: str) -> None:
    assert _answer(text) == answer


def test_a_braking_force_stays_a_size_with_its_direction() -> None:
    """A force's sign is the axis's: the 2026-11-07 sizes-and-directions rule stands."""
    answer = _answer(
        "A 1000 kg car slows from 20 m/s to rest in 5 s. What is the average braking force?"
    )
    assert answer is not None and not answer.startswith("-"), answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # The fall word governs the value, however far the sample's words put it.
        (
            "A fridge cools 2 kg of water by 15 °C. How much heat is removed from the water?",
            "-125580 J (released)",
        ),
        (
            "How much heat must be removed to lower the temperature of 2 kg of water by 30 °C?",
            "-251160 J (released)",
        ),
        (
            "How much heat is released by 2 kg of water for a 10 °C drop in temperature?",
            "-83720 J (released)",
        ),
        # Work on or by a gas stays a size with its word: which it is, is the ask's choice.
        (
            "2 mol of an ideal gas is compressed isothermally at 300 K from 0.04 m^3 to "
            "0.01 m^3. How much work is done on the gas?",
            "6916 J (done on the gas)",
        ),
    ],
)
def test_a_fall_is_read_where_its_word_governs_the_value(text: str, answer: str) -> None:
    assert _answer(text) == answer


def test_a_rise_after_a_falling_body_stays_a_rise() -> None:
    """Review: "dropped from 20 m and its temperature rises by 3 °C" was -780 J (released)."""
    from app.modules.physics.prompt import solve_physics_request

    text = (
        "A 2 kg lead ball is dropped from 20 m and its temperature rises by 3 °C on impact. "
        "c = 130 J/kg°C. (a) How fast does it hit the ground? (b) How much heat does it absorb?"
    )
    _outcome, block = solve_physics_request(text, Settings(math_tools_enabled=True), None)
    assert block is not None and block.canonical_answer == "19.8 m/s; 780 J"


def test_the_size_of_heat_given_off_is_a_right_claim() -> None:
    """Review: "I got 7700 J for the heat given off" is the textbook answer, not wrong."""
    from app.modules.physics.direct import _claim_line
    from app.modules.physics.prompt import solve_physics_request

    text = (
        "A 200 g copper block cools from 100 °C to 0 °C (c = 385 J/kg °C). I got 7700 J for "
        "the heat given off. Am I right?"
    )
    _outcome, block = solve_physics_request(text, Settings(math_tools_enabled=True), None)
    assert block is not None
    assert _claim_line(block, text) == "Your 7700 J is right."
    wrong = text.replace("7700 J", "7000 J")
    assert _claim_line(block, wrong) == "Your 7000 J is not right; the verified answer is below."


@pytest.mark.parametrize(
    ("text", "size", "signed"),
    [
        # Codex on #2507: a drop of the same number in metres is not the temperature's.
        (
            "A 2 kg block drops by 10 m and its temperature rises by 10 °C. How much heat "
            "does it absorb?",
            10.0,
            10.0,
        ),
        ("The temperature of 3 kg of water decreases by 10 °C.", 10.0, -10.0),
        ("Heat released by 2 kg of water for a 10 °C drop in temperature.", 10.0, -10.0),
    ],
)
def test_only_the_temperature_s_own_value_is_signed(text: str, size: float, signed: float) -> None:
    from app.modules.physics.extractors.thermal import _signed_change

    assert _signed_change(text, size) == signed
