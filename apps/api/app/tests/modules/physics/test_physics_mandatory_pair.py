"""The car that stops and the car at constant speed are never confused (audit 2026-11-07).

Two questions with the same numbers and different motion: one stops (u = 20, v = 0, a
constant deceleration), the other keeps its speed. Each stage is held, not only the final
number: the values read and their units, what is asked, the law chosen, the answer, and
that it is verified.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.solver import solve_physics


@dataclass(frozen=True)
class Expected:
    law: str
    givens: dict[str, tuple[float, str]]
    answer: str


_LENGTH = "[length]^1"

PAIR = {
    "A car travels at 20 m/s and takes 5 seconds to stop. How far does it travel?": Expected(
        law="suvat_distance",
        givens={"u": (20.0, "m/s"), "v": (0.0, "m/s"), "t": (5.0, "seconds")},
        answer="50 m",
    ),
    "A car travels at a constant speed of 20 m/s for 5 seconds. How far does it travel?": Expected(
        law="rate_distance",
        givens={"v": (20.0, "m/s"), "t": (5.0, "s")},
        answer="100 m",
    ),
}


@pytest.mark.parametrize(("question", "expected"), PAIR.items(), ids=["stops", "constant"])
def test_each_stage_of_the_pair(question: str, expected: Expected) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None, "read as a physics question"
    # What is asked: a distance.
    assert list(intent.asked) == [_LENGTH]
    # The law follows the motion: a stop is a constant deceleration, not d = vt.
    assert intent.physics_op == expected.law
    # The values read, with their units, and nothing invented.
    units = intent.physics_units or {}
    read = {
        name: (value, units.get(name, ""))
        for name, value in (intent.physics_params or {}).items()
        if name in expected.givens
    }
    assert read == expected.givens
    result = solve_physics(intent)
    assert (result.answer_value or result.answer) == expected.answer


def test_the_pair_is_answered_differently() -> None:
    stops, constant = (extract_physics_intent(question) for question in PAIR)
    assert stops is not None and constant is not None
    assert stops.physics_op != constant.physics_op
