"""A line that changes the chat's last money request, and the look-alikes that change none.

Live (2026-10-25): "hmm what if i only do 3 years instead" after a used-car loan got no
card, and the model's own arithmetic was off by dollars.
"""

from __future__ import annotations

import pytest

from app.modules.money.follow_up import follow_up_request
from app.modules.money.read import read_money_request

USED = (
    "i'm thinking of buying a used car for 14000, i can put 3000 down. what would my monthly "
    "payment be over 5 years?"
)
CAR = "car loan 14000 with 3000 down at 7.16% for 5 years, what's the monthly payment"
MORTGAGE = "what is my mortgage for 300k dollars house if mr rate is 1 percent"
CARD = "I owe 5000 on my credit card at 22% apr and pay 200 a month, how long to pay off"
SAVINGS = "if I save 200 a month at 4.5% for 10 years how much will I have"
WORKOUT = "give me a 4 day workout plan with 4 sets of each exercise"
RECTANGLE = "a rectangle has a perimeter of 40 and a length of 12, what is the width?"


@pytest.mark.parametrize(
    ("earlier", "line", "values", "changed"),
    [
        # The live line: the used car over 36 months, its rate still today's average.
        ([USED], "hmm what if i only do 3 years instead", {"amount": 11000, "months": 36}, ("months",)),
        ([CAR], "hmm what if i only do 3 years instead", {"amount": 11000, "months": 36, "rate": 7.16}, ("months",)),
        ([CAR], "what if i do 3 years instead of 5", {"months": 36}, ("months",)),
        ([CAR], "what if I go from 60 to 36 months", {"months": 36}, ("months",)),
        ([CAR], "36 months?", {"months": 36}, ("months",)),
        ([CAR], "make it 4 years", {"months": 48}, ("months",)),
        ([CAR], "what if I pay it off in 2 years", {"months": 24}, ("months",)),
        ([CAR], "what if I went with a 4 year loan", {"months": 48}, ("months",)),
        ([CAR], "what would it be at 5%?", {"rate": 5, "amount": 11000}, ("rate",)),
        ([CAR], "what if I put 5000 down?", {"amount": 9000}, ("down",)),
        ([CAR], "what if I put down 5000", {"amount": 9000}, ("down",)),
        ([CAR], "what if I put 20% down?", {"amount": 11200}, ("down",)),
        ([CAR], "what if the car was $18,000?", {"amount": 15000}, ("amount",)),
        ([CAR], "what if I only borrow 8000?", {"amount": 8000}, ("amount",)),
        # A sum named as the loan is what is borrowed, with nothing taken off.
        ([CAR], "what if I get a 25000 car loan at 5% for 4 years", {"amount": 25000, "rate": 5, "months": 48}, ("rate", "months", "amount")),
        ([CAR], "and 5000 down?", {"amount": 9000}, ("down",)),
        ([CAR], "$18,000?", {"amount": 15000}, ("amount",)),
        ([CAR], "what if I put 5000 down over 4 years at 6%", {"amount": 9000, "months": 48, "rate": 6}, ("rate", "months", "down")),
        ([CAR], "what if it was a used car?", {"amount": 11000, "months": 60}, ("variant",)),
        ([MORTGAGE], "what about 15 years?", {"amount": 300000, "rate": 1, "years": 15}, ("years",)),
        ([MORTGAGE], "what if the rate was 6.5%?", {"rate": 6.5}, ("rate",)),
        ([MORTGAGE], "what about a 15 year mortgage at 5.5%?", {"rate": 5.5, "years": 15}, ("rate", "years")),
        ([MORTGAGE], "what if I put 20% down", {"amount": 240000}, ("down",)),
        ([CARD], "what if I pay 300 a month instead?", {"balance": 5000, "payment": 300}, ("payment",)),
        ([CARD], "what if I pay 300 instead", {"payment": 300}, ("payment",)),
        ([SAVINGS], "what about 20 years?", {"deposit": 200, "years": 20}, ("years",)),
        ([SAVINGS], "what if I save 300 a month instead", {"deposit": 300, "years": 10}, ("deposit",)),
        ([SAVINGS], "what if I save 300 instead", {"deposit": 300}, ("deposit",)),
        # Each change builds on the one before it.
        ([CAR, "what if i only do 3 years instead"], "and with 5000 down?", {"amount": 9000, "months": 36}, ("down",)),
    ],
)  # fmt: skip
def test_a_change_line_is_the_last_request_changed(
    earlier: list[str], line: str, values: dict[str, float], changed: tuple[str, ...]
) -> None:
    request = follow_up_request(line, earlier)
    assert request is not None
    assert {name: request.values.get(name) for name in values} == values
    assert request.changed == changed


@pytest.mark.parametrize(
    ("earlier", "line"),
    [
        # Not a money chat, or one that moved on.
        ([WORKOUT], "what if i only do 3 sets instead"),
        (["what's a good name for a cat"], "3 years"),
        ([], "3 years"),
        ([RECTANGLE], "what if the perimeter was 48?"),
        ([CAR, "how do I make lasagna?"], "what if i only do 3 years instead"),
        # Too far back: the request is not in the last three lines.
        (
            [CAR, "what if 3 years instead", "and 4 years?", "ok and 5000 down"],
            "what about 72 months",
        ),
        # A money chat, but the line changes none of the request's inputs.
        ([CAR], "what if i only do 3 sets instead"),
        ([CAR], "what if it was 3 years ago"),
        ([CAR], "what if I was 30 years old"),
        ([CAR], "what if I was 3 years older"),
        ([CAR], "what if I wait 2 years to buy"),
        ([CAR], "what if I keep the car for 10 years"),
        ([CAR], "what if I retire in 10 years"),
        ([CAR], "what if I'm 3 years into the loan"),
        ([MORTGAGE], "what if I sell after 5 years?"),
        ([CAR], "what if I made 50k a year?"),
        ([CAR], "what if my salary was 50k"),
        ([CAR], "can I afford it on a 50k salary?"),
        ([CAR], "what about a 2019 civic?"),
        ([CAR], "is 7% a good rate?"),
        ([CAR], "thanks, that helps"),
        ([CAR], "lol 100%"),
        ([CAR], "100%"),
        ([CAR], "ok 5 stars"),
        ([CAR], "what if I pay 500 a month"),
        # A change by an amount is not worked out here.
        ([CAR], "what if rates drop 1% next year?"),
        ([CAR], "what if the rate was 1% lower"),
        ([CAR], "what if I put 2000 more down"),
        # Another product is a new question.
        ([MORTGAGE], "what about a car loan at 5% instead?"),
        # A rates question is no request to change.
        (["what are car loan rates right now"], "what about 72 months?"),
    ],
)
def test_a_line_that_changes_no_request_is_none(earlier: list[str], line: str) -> None:
    assert follow_up_request(line, earlier) is None


def test_a_new_term_keeps_the_average_the_last_reply_used() -> None:
    """The rate was today's 60-month average: 36 months keeps it, so only the term changes."""
    request = follow_up_request("hmm what if i only do 3 years instead", [USED])
    assert request is not None
    assert request.variant == "used" and request.rate_term == 60 and "rate" not in request.values
    given = follow_up_request("what if i only do 3 years at 6%", [USED])
    assert given is not None and given.rate_term is None


def test_a_first_ask_is_no_follow_up() -> None:
    """The reader of a request alone stays as it was; the follow-up is the turn's to ask."""
    assert follow_up_request(CAR, []) is None
    first = read_money_request(CAR)
    assert first is not None and first.changed == () and first.down == 3000
