"""A science's problem is never a money request, whatever "car" or "40%" it holds.

"A screw jack has a pitch of 5 mm and a handle 35 cm long. It's efficiency is 40%. What
effort ... to lift a car weighing 9000 N?" got a car-loan card (amount $5, the pitch, at
40%) and a note that 40% is no realistic car-loan rate (2026-11-18). Money yields a line
the subject order reads as physics or chemistry; maths keeps its money lines.
"""

from __future__ import annotations

import pytest

from app.core.readings import begin_turn
from app.modules.money import subject as money_subject
from app.services.subjects.registry import MONEY

_SCREW_JACK = (
    "A screw jack has a pitch of 5 mm and a handle 35 cm long. It's efficiency is 40%. "
    "What effort at the end of the handle is needed to lift a car weighing 9000 N?"
)


@pytest.mark.parametrize(
    ("text", "money"),
    [
        (_SCREW_JACK, False),
        ("A 1200 kg car accelerates from rest to 25 m/s in 10 s. What is the net force?", False),
        ("A $20,000 car loan at 6% for 60 months. What is the monthly payment?", True),
        # A card payoff the order reads as maths is still the money card's.
        (
            "I owe $5,000 on my credit card at 22% APR and pay $200 a month. "
            "How long to pay it off?",
            True,
        ),
    ],
)
def test_money_yields_a_sciences_problem(text: str, money: bool) -> None:
    begin_turn()
    money_subject._reads_money.cache_clear()
    assert MONEY.reads(text) is money


@pytest.mark.parametrize(
    ("subject", "yields"),
    [("physics", True), ("chemistry", True), ("math", False), (None, False)],
)
def test_money_yields_only_to_the_sciences(subject: str | None, yields: bool) -> None:
    assert MONEY.yields_to(subject) is yields
