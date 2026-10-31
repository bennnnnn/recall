"""Circuit givens read whole: a resistor named again is one resistor, a part's label is no
unit, and two values of one quantity are no single law's (2026-10-30, a Grade 10 physics
book's circuits, three of which were certified wrong)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(mock_llm_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Certified 200 Ω: "the 50 Ω resistor" in part (c) was a third resistor.
        (
            "In the circuit the battery has negligible internal resistance. Calculate: a) the "
            "total resistance in the circuit c) the potential difference across the 50 Ω "
            "resistor. [Figure: a 3 V battery with a 50 Ω resistor and a 100 Ω resistor in "
            "series.]",
            150.0,
        ),
        ("A 6 Ω and a 6 Ω resistor are connected in series. Find the total resistance.", 12.0),
        (
            "A 10 Ω resistor and a 20 Ω resistor are joined in series. What is the total "
            "resistance of the 10 Ω resistor and the 20 Ω resistor together?",
            30.0,
        ),
    ],
)
def test_a_resistor_named_again_is_one_resistor(text: str, value: float) -> None:
    answer = _answer(text)
    assert answer is not None, text
    assert answer_number(answer) == pytest.approx(value), answer


@pytest.mark.parametrize(
    "text",
    [
        # Certified 0.952 Ω: "12.6 a) Draw…" read as 12.6 A beside the bulb's 12 V rating.
        "A 12 V light bulb is put under test, with the following results: Current through "
        "bulb (A): 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6 p.d. across bulb (V): 1.4, 2.6, 3.9, 5.5, "
        "7.4, 9.7, 12.6\na) Draw the circuit you would use. b) Work out the resistance R of "
        "the bulb for each set of readings.",
        # Certified 6 Ω: an unknown R beside "the 3 Ω resistor" named twice.
        "a) What current is flowing round the circuit? b) How great must the p.d. be across "
        "resistor R? c) What is the resistance of resistor R? [Figure: a 48 V battery in "
        "series with a 3 Ω resistor and a resistor R; a voltmeter across the 3 Ω resistor "
        "reads 9 V.]",
        # Two voltages: which one Ohm's law takes is a guess.
        "A 12 V battery is connected to a 4 Ω lamp, and a voltmeter across the lamp reads 10 V. "
        "Find the current.",
    ],
)
def test_a_circuit_read_in_part_declines(text: str) -> None:
    assert _answer(text) is None


def test_a_bracketed_unit_is_still_a_unit() -> None:
    answer = _answer("A current (2 A) flows through a 6 Ω resistor. Find the voltage.")
    assert answer is not None
    assert answer_number(answer) == pytest.approx(12.0)
