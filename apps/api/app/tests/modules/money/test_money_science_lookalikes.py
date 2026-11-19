"""A science's problem is never a money request, whatever "car" or "40%" it holds.

"A screw jack has a pitch of 5 mm and a handle 35 cm long. It's efficiency is 40%. What
effort ... to lift a car weighing 9000 N?" got a car-loan card (amount $5, the pitch, at
40%) and a note that 40% is no realistic car-loan rate (2026-11-18). Money yields a line
the subject order reads as physics or chemistry, unless the line names money outright: a
card payoff physics also reads ("$3,000 at 18% APR") is still the card's, and maths keeps
its money lines.
"""

from __future__ import annotations

import pytest

from app.services.subjects.order import read_subject_reason
from app.services.subjects.registry import MONEY

_SCREW_JACK = (
    "A screw jack has a pitch of 5 mm and a handle 35 cm long. It's efficiency is 40%. "
    "What effort at the end of the handle is needed to lift a car weighing 9000 N?"
)


@pytest.mark.parametrize(
    ("text", "yields"),
    [
        (_SCREW_JACK, True),
        ("A 1200 kg car accelerates from rest to 25 m/s in 10 s. What is the net force?", True),
        ("A $20,000 car loan at 6% for 60 months. What is the monthly payment?", False),
        (
            "Tom has a credit card balance of $3,000 at 18% APR and pays $100 a month. "
            "How long until it is paid off?",
            False,
        ),
        # A saving names its product by its own word, with no currency: still the card's.
        ("If I save 200 a month at a rate of 6% per year, how long to reach 50000?", False),
        ("I save 300 a month at 5% a year. How long until I reach 20000?", False),
    ],
)
def test_money_yields_a_sciences_problem_that_names_no_money(text: str, yields: bool) -> None:
    read = read_subject_reason(text, False, True)
    subject = None if read is None else read.subject
    assert MONEY.yields_to(text, subject) is yields


@pytest.mark.parametrize(
    ("subject", "yields"),
    [("physics", True), ("chemistry", True), ("math", False), (None, False)],
)
def test_money_yields_only_to_the_sciences(subject: str | None, yields: bool) -> None:
    assert MONEY.yields_to("A car engine is 30% efficient.", subject) is yields


def test_a_science_line_that_names_money_stays_money() -> None:
    assert not MONEY.yields_to("A $20,000 car loan at 6%.", "physics")
