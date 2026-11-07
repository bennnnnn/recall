"""A quantity written in words is read as its number, or the question declines.

"A ball is dropped from ten metres onto a 1 m table" was solved with the 1 m: the
reader never saw "ten metres". Answers worked by hand, g = 9.81 m/s².
"""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(math_tools_enabled=True)
_G = 9.81


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        (
            "A ball is dropped from ten metres. How long does it take to hit the ground?",
            math.sqrt(2 * 10 / _G),
            "s",
        ),
        (
            "A ball is dropped from a height of ten meters. How fast does it hit the ground?",
            math.sqrt(2 * _G * 10),
            "m/s",
        ),
        (
            "A ball is dropped from a height of twenty-five metres. How long does it take to hit the ground?",
            math.sqrt(2 * 25 / _G),
            "s",
        ),
        ("A ball is thrown up at fifteen m/s. How high does it go?", 15**2 / (2 * _G), "m"),
        (
            "A car accelerates from rest at two m/s^2 for ten seconds. How far does it travel?",
            100.0,
            "m",
        ),
        ("A car travels a hundred metres in 5 s. What is its average speed?", 20.0, "m/s"),
        (
            "A train travels three hundred kilometres in two hours. What is its average speed?",
            150.0,
            "km/h",
        ),
    ],
)
def test_a_number_in_words_is_read(text: str, value: float, unit: str) -> None:
    answer = _answer(text)
    assert answer is not None, f"no verified answer for {text!r}"
    assert math.isclose(answer_number(answer), value, rel_tol=0.01), (text, answer, value)
    assert unit in answer, (text, answer)


@pytest.mark.parametrize(
    "text",
    [
        # Read, the 10 m fall is two heights: the table's 1 m alone is never the fall.
        "A ball is dropped from ten metres onto a 1 m table. How long does it take to reach the table?",
        # An amount that says no one number declines the whole question.
        "A ball is dropped from a few metres onto a 1 m table. How long does it take to reach the table?",
        "A ball is dropped from several metres. How long does it take to hit the ground?",
    ],
)
def test_a_number_in_words_is_never_skipped(text: str) -> None:
    answer = _answer(text)
    assert answer is None or not math.isclose(
        answer_number(answer), math.sqrt(2 * 1 / _G), rel_tol=0.01
    ), (text, answer)
    if "few" in text or "several" in text:
        assert answer is None, (text, answer)
