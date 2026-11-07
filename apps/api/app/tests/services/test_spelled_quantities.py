"""A number written in words beside its unit is read, or flagged so the question declines."""

from __future__ import annotations

import pytest

from app.modules.physics.numbers import quantity_unit_at as unit_at
from app.services.number_text import spelled_quantities, spelled_value


@pytest.mark.parametrize(
    ("words", "value"),
    [
        ("ten", 10),
        ("twenty five", 25),
        ("twenty-five", 25),
        ("hundred", 100),
        ("two hundred and fifty", 250),
        ("one thousand two hundred", 1200),
        ("five ten", None),
        ("twenty thirty", None),
        ("ten five", None),
    ],
)
def test_spelled_value(words: str, value: int | None) -> None:
    assert spelled_value(words) == value


@pytest.mark.parametrize(
    ("text", "read", "unread"),
    [
        (
            "dropped from ten metres onto a 1 m table",
            "dropped from 10 metres onto a 1 m table",
            False,
        ),
        ("a hundred m in 5 s", "100 m in 5 s", False),
        ("twenty-five m/s", "25 m/s", False),
        ("two and a half m", "2.5 m", False),
        ("a ten-metre ladder", "a 10 metre ladder", False),
        ("five kilograms of sand", "5 kilograms of sand", False),
        # Not a quantity: no unit follows the number word.
        ("one in ten people", "one in ten people", False),
        ("three times as fast", "three times as fast", False),
        ("how many kWh does it use", "how many kWh does it use", False),
        ("completing one turn every 2 s", "completing one turn every 2 s", False),
        ("in half an hour", "in 0.5 hour", False),
        ("the second one is 3 m away", "the second one is 3 m away", False),
        # An amount in words that says no one number: the caller declines.
        ("a few metres", "a few metres", True),
        ("several kg", "several kg", True),
        ("five ten m", "five ten m", True),
    ],
)
def test_spelled_quantities(text: str, read: str, unread: bool) -> None:
    spelled = spelled_quantities(text, unit_at)
    assert (spelled.text, spelled.unread) == (read, unread)
