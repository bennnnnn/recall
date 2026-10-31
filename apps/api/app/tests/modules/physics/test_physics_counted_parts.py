"""Counted circuit parts: one value stated for several parts is that value in each.

"Two resistors, each with a resistance of 10 Ω, in parallel across 5 V" verified 0.5 A,
the current of one resistor (2026-10-31). Every way of saying the count reads the same, and
a count the question leaves unclear declines instead of reading one part.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.extractors.counted_parts import CountedPart, counted_parts
from app.tests.modules.physics.support import build_verified_physics_block, extract_physics_intent


def _verified_answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    "text,answer",
    [
        (
            "Two resistors, each with a resistance of 10 Ω, are connected in parallel across "
            "5 V. What is the total current?",
            "1 A",
        ),
        (
            "Two resistors of 10 Ω each are connected in parallel across a 5 V battery. "
            "Find the total current.",
            "1 A",
        ),
        (
            "Each of the two resistors has a resistance of 10 Ω. They are connected in parallel "
            "to a 5 V supply. What is the current from the supply?",
            "1 A",
        ),
        ("Two 10-ohm resistors are connected in series across 12 V. Find the current.", "0.6 A"),
        ("Two 10 Ω resistors are connected in parallel across 5 V. Find the total current.", "1 A"),
        (
            "Three identical resistors of 6 Ω are connected in series. What is the total "
            "resistance?",
            "18 Ω",
        ),
        (
            "Three resistors, each 4 Ω, are connected in parallel. Find the equivalent resistance.",
            "1.33 Ω",
        ),
        (
            "A 4 Ω resistor is in series with two resistors of 6 Ω each in parallel. Find the "
            "total resistance.",
            "7 Ω",
        ),
    ],
)
def test_a_value_stated_for_counted_resistors_is_in_each(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # One value, two resistors, and "each" unsaid: 10 Ω each, or in all?
        "Two resistors of 10 Ω are connected in parallel across 5 V. What is the total current?",
        # "Each", but not how many.
        "Resistors of 10 Ω each are connected in parallel across 5 V. Find the total current.",
        # How they are wired is not said.
        "Two resistors, each 10 Ω, are connected to a 5 V battery. What is the current?",
        # No reader takes the power of a network: it must not take one resistor's.
        "Two resistors, each of 10 Ω, are in series with a 12 V battery. Find the power "
        "dissipated.",
        # Cells, capacitors and lamps: no reader combines them, so none reads one of them.
        "Two 1.5 V cells in series are connected to a 3 Ω resistor. What is the current?",
        "A pair of 1.5 V cells powers a 3 Ω lamp. What is the current?",
        "Two capacitors of 10 µF each are charged to 12 V. Find the energy stored.",
        "Two 60 W bulbs are left on for 5 hours. How much electrical energy do they use?",
    ],
)
def test_a_counted_part_a_reader_cannot_account_for_declines(text: str) -> None:
    assert _verified_answer(text) is None


@pytest.mark.parametrize(
    "text,answer",
    [
        # A count of something that is not a part.
        (
            "A 10 Ω resistor is connected across 5 V. What is the current through each of the "
            "two wires?",
            "0.5 A",
        ),
        # Counted parts with no value of their own: the values are the circuit's.
        (
            "Two bulbs are connected in parallel to a 12 V battery and draw 2 A in total. What "
            "is the total resistance?",
            "6 Ω",
        ),
        # Every counted resistor's value stated.
        (
            "Two resistors of 4 Ω and 6 Ω are connected in series across 10 V. Find the current.",
            "1 A",
        ),
        (
            "Three resistors of 2, 3 and 6 ohms are connected in parallel. Find the total "
            "resistance.",
            "1 Ω",
        ),
    ],
)
def test_counts_that_name_no_shared_value_read_as_before(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


@pytest.mark.parametrize(
    "text,parts",
    [
        ("each of the two resistors is 10 Ω", [CountedPart("resistor", 2, 10.0)]),
        ("two resistors of 10 Ω each", [CountedPart("resistor", 2, 10.0)]),
        ("three identical resistors of 6 ohms", [CountedPart("resistor", 3, 6.0)]),
        ("2 identical 4.5 V batteries", [CountedPart("cell", 2, 4.5)]),
        ("both capacitors are 5 µF", [CountedPart("capacitor", 2, None)]),
        ("two resistors of 4 Ω and 6 Ω", [CountedPart("resistor", 2, None)]),
        ("resistors of 10 Ω each", [CountedPart("resistor", None, None)]),
        ("each of the two wires is 3 m long", []),
        ("the 2 Ω and 3 Ω resistors", []),
    ],
)
def test_counted_parts_reads_the_count_and_the_shared_value(
    text: str, parts: list[CountedPart]
) -> None:
    assert counted_parts(text) == parts
