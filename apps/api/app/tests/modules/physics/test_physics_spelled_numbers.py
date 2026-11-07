"""A quantity written in words is never read: the question declines (``spelled.py``).

"A ball is dropped from ten metres onto a 1 m table" was solved with the 1 m: the
reader never saw "ten metres". Reading the words went wrong too ("1.5 thousand metres"
was 1000 m, "two point five metres" 5 m, "one second later" a time of the fall).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.numbers import quantity_unit_at
from app.modules.physics.spelled import has_unread_quantity

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("text", "unread"),
    [
        ("ten metres", True),
        ("twenty-five m/s", True),
        ("1.5 thousand metres", True),
        ("2 hundred metres", True),
        ("1.2 million", True),
        ("two point five metres", True),
        ("one-and-a-half metres", True),
        ("three quarters of a metre", True),
        ("half a lap", True),
        ("half a second", True),
        ("half the distance of 100 m", True),
        ("half the time and 60 km/h for the other half", False),
        ("one second later", True),
        ("a ten-metre board", True),
        ("twelve hundred kg", True),
        ("a few metres", True),
        ("One mole of an ideal gas", True),
        # Not quantities: an ordinal, a pronoun, a count, a question word.
        ("a second ball", False),
        ("the one on the left", False),
        ("one of the 2 kg blocks", False),
        ("completing one turn every 2 s", False),
        ("from zero to 27 m/s", False),
        ("how many kWh", False),
    ],
)
def test_a_spelled_quantity_is_unread(text: str, unread: bool) -> None:
    assert has_unread_quantity(text, quantity_unit_at) is unread


@pytest.mark.parametrize(
    "text",
    [
        "A ball is dropped from ten metres onto a 1 m table. How long does it take to reach the table?",
        "A ball is dropped from ten metres. How long does it take to hit the ground?",
        "A car travels at twenty-five m/s for ten seconds. How far does it go?",
        "A car travels 2.5 thousand metres in 100 s. Find its average speed.",
        "A ball is dropped from 2 hundred metres. How long does it take to fall?",
        "A ball is dropped from two point five metres. How long does it take to fall?",
        "A runner at five m/s runs half a lap of a 400 m track. How long does it take?",
        "A car covers half the distance of 100 m at 10 m/s. How long does that take?",
        "A ball is dropped from 45 m. One second later a second ball is dropped. "
        "How fast does the first ball hit the ground?",
        "A heater supplies 2.4 thousand joules to 1 kg of water at 20 °C. Find the final temperature.",
        "A ball is dropped from a few metres above a 1 m table. How long to hit the table?",
    ],
)
def test_a_question_with_a_spelled_quantity_declines(text: str) -> None:
    assert _answer(text) is None, (text, _answer(text))


def test_a_count_in_words_is_still_read() -> None:
    answer = _answer(
        "A stone on a 1.5 m string is whirled in a horizontal circle, completing one turn "
        "every 2 s. what is its speed?"
    )
    assert answer is not None and answer.startswith("4.71")
