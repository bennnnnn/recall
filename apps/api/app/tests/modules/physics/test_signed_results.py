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
