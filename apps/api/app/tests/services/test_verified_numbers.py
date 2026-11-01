"""A verified card whose solve did not read a number or count the question states is
dropped (``services/verified_numbers.py``), in the gate's two modes.

The cards here are the reviews' (#2172): each one the solve gave while ignoring a count
or a number, and the look-alikes that must keep their card.
"""

from __future__ import annotations

from typing import Literal

import pytest

from app.core.config import Settings
from app.services.subject_solving import build_subject_augmentation

# A count whose items each have a value the solve read once: wrong in both modes.
COUNTED = [
    "Twenty 60 W bulbs are on for 5 hours. Find the energy used.",
    "20 identical 60 W bulbs are on for 5 hours. Find the energy used.",
    "A dozen 60 W bulbs are on for 5 hours. Find the energy used.",
    "Several 60 W bulbs are on for 5 hours. Find the energy used.",
    "Many 2 kg bricks are lifted 3 m. Find the potential energy gained.",
    "Both of the resistors are 10 Ω and are connected in parallel across 5 V. Find the total current.",
    "Both of my phones charge at 20 W. How much energy do they use in 2 hours?",
    "Two horses each pull a cart with a force of 400 N. The cart has a mass of 200 kg. Find the acceleration.",
]
# A number the solve did not read: dropped only when every number is held to it.
NUMBERS = [
    "What is the total mass of 2 moles of NaCl and 3 moles of water?",
    "If you remove 5 from it, what is 25% of 80?",
]
# Counts the solve did read, or that give no value each: kept in both modes.
KEPT = [
    ("Two 10 Ω resistors are connected in parallel across 5 V. Find the current.", "1 A"),
    ("Two charges of 3 µC each are placed 0.5 m apart. Find the force between them.", "0.324 N"),
    (
        "Two trains are 300 km apart and head toward each other at 80 km/h and 70 km/h. "
        "When do they meet?",
        "7200 s",
    ),
    (
        "A 12 V battery has two cells. A 6 Ω resistor is connected across it. Find the current.",
        "2 A",
    ),
    ("Two 500 mΩ resistors are connected in series. Find the total resistance.", "1 Ω"),
    ("what is 1.8 x 10^-5 times 2", None),
]


Gate = Literal["off", "counts", "all"]


async def _card(text: str, gate: Gate) -> str | None:
    settings = Settings(
        math_llm_extract_enabled=False, math_word_problems_enabled=False, verified_numbers_gate=gate
    )
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", ["counts", "all"])
@pytest.mark.parametrize("text", COUNTED)
async def test_a_card_that_reads_one_of_many_items_is_dropped(
    thread_sympy_executor: None, text: str, gate: Gate
) -> None:
    assert await _card(text, "off") is not None
    assert await _card(text, gate) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("text", NUMBERS)
async def test_a_card_that_skips_a_number_is_dropped_only_when_every_number_counts(
    thread_sympy_executor: None, text: str
) -> None:
    assert await _card(text, "counts") is not None
    assert await _card(text, "all") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", ["counts", "all"])
@pytest.mark.parametrize(("text", "answer"), KEPT)
async def test_a_card_that_reads_every_count_is_kept(
    thread_sympy_executor: None, text: str, answer: str | None, gate: Gate
) -> None:
    card = await _card(text, gate)
    assert card is not None
    if answer is not None:
        assert card == answer
