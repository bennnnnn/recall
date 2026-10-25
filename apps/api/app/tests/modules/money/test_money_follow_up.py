"""A line that changes the chat's last money request's term or rate, and every line that
changes something else, which goes to the model.

Live (2026-10-25): "hmm what if i only do 3 years instead" after a used-car loan got no
card, and the model's own arithmetic was off by dollars. Three reviews of wider readers
(same day) each found a new shape they misread as a price, a down payment, a payment or
a kind: "it's 40k miles", "what if I pay 400 instead?", "what about a 2019 model?", "what
if my payment is 3%". The server now works a new term or rate only, read by a positive
grammar (``change_line``): a line with any word it does not place is no follow-up.
"""

from __future__ import annotations

import pytest

from app.modules.money.change_line import read_change
from app.modules.money.follow_up import follow_up_request
from app.modules.money.read import read_money_request

USED = (
    "i'm thinking of buying a used car for 14000, i can put 3000 down. what would my monthly "
    "payment be over 5 years?"
)
CAR = "car loan 14000 with 3000 down at 7.16% for 5 years, what's the monthly payment"
CAR_PLAIN = "car loan 20000 at 7% for 5 years, what's the monthly payment"
USED_8 = "used car loan 8000 at 9% for 48 months"
MORTGAGE = "what is my mortgage for 300k dollars house if mr rate is 1 percent"
MORTGAGE_6 = "mortgage of 300k at 6% for 30 years"
MORTGAGE_SHARE = "what would my mortgage payment be on a 350k house with 20% down"
CARD = "I owe 5000 on my credit card at 22% apr and pay 200 a month, how long to pay off"
SAVINGS = "if I save 200 a month at 4.5% for 10 years how much will I have"
SAVINGS_1K = "if I save 1000 a month at 5% for 20 years how much will I have"
PERSONAL = "personal loan of 10000 at 12% for 36 months"
STUDENT = "student loan of 30000 at 5.5% for 10 years"
BIRR = "mortgage of 3 million birr at 15% for 20 years"
WORKOUT = "give me a 4 day workout plan with 4 sets of each exercise"
RECTANGLE = "a rectangle has a perimeter of 40 and a length of 12, what is the width?"


@pytest.mark.parametrize(
    ("earlier", "line", "values", "changed"),
    [
        # The live line: the used car over 36 months, its rate still today's average.
        ([USED], "hmm what if i only do 3 years instead", {"amount": 11000, "months": 36}, ("months",)),
        ([CAR], "hmm what if i only do 3 years instead", {"amount": 11000, "months": 36, "rate": 7.16}, ("months",)),
        ([CAR], "what if i do 3 years instead of 5", {"months": 36}, ("months",)),
        ([CAR], "36 months?", {"months": 36}, ("months",)),
        ([CAR], "make it 4 years", {"months": 48}, ("months",)),
        ([CAR], "and over 4 years?", {"months": 48}, ("months",)),
        ([CAR], "what if I pay it off in 2 years", {"months": 24}, ("months",)),
        ([CAR], "what if I went with a 4 year loan", {"months": 48}, ("months",)),
        ([CAR], "same thing but 4 years", {"months": 48}, ("months",)),
        ([CAR_PLAIN], "what about 36mo", {"months": 36}, ("months",)),
        ([MORTGAGE], "what about 15 years?", {"amount": 300000, "rate": 1, "years": 15}, ("years",)),
        ([MORTGAGE_6], "what about 180 months", {"years": 15}, ("years",)),
        ([MORTGAGE_6], "what if I take 15 years", {"years": 15}, ("years",)),
        ([MORTGAGE_SHARE], "what about 15 years", {"amount": 280000, "years": 15}, ("years",)),
        ([STUDENT], "what if it's 20 years", {"years": 20}, ("years",)),
        ([PERSONAL], "what about 60 months", {"months": 60}, ("months",)),
        ([SAVINGS], "what about 20 years?", {"deposit": 200, "years": 20}, ("years",)),
        ([SAVINGS], "what if I save for 20 years", {"years": 20}, ("years",)),
        # A rate by its words, or a line that is only a percent.
        ([CAR], "what would it be at 5%?", {"rate": 5, "amount": 11000}, ("rate",)),
        ([CAR], "same but at 5%", {"rate": 5}, ("rate",)),
        ([CAR], "7%", {"rate": 7}, ("rate",)),
        ([CAR], "what if it's 5%", {"rate": 5}, ("rate",)),
        ([CAR], "what if the interest rate was 6%", {"rate": 6}, ("rate",)),
        ([MORTGAGE], "what if the rate was 6.5%?", {"rate": 6.5}, ("rate",)),
        ([MORTGAGE_SHARE], "5%?", {"amount": 280000, "rate": 5}, ("rate",)),
        ([CARD], "what if the apr was 18%", {"apr": 18}, ("apr",)),
        ([CARD], "what about 15% apr", {"apr": 15}, ("apr",)),
        ([STUDENT], "what if it was 6.8%", {"rate": 6.8}, ("rate",)),
        ([SAVINGS], "what about 8%", {"rate": 8}, ("rate",)),
        # Both, in the loan's own words.
        ([MORTGAGE], "what about a 15 year mortgage at 5.5%?", {"rate": 5.5, "years": 15}, ("rate", "years")),
        ([PERSONAL], "what about 24 months at 10%", {"rate": 10, "months": 24}, ("rate", "months")),
        # Each change builds on the one before it.
        ([CAR, "what if i only do 3 years instead"], "and at 5%?", {"rate": 5, "months": 36}, ("rate",)),
    ],
)  # fmt: skip
def test_a_new_term_or_rate_is_the_last_request_changed(
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
        (
            [CAR, "what if 3 years instead", "and 4 years?", "ok and 5000 down"],
            "what about 72 months",
        ),
        (["what are car loan rates right now"], "what about 72 months?"),
        # A length of time that is not the loan's, or one no slider of it reaches.
        ([CAR], "what if it was 3 years ago"),
        ([CAR], "what if I was 30 years old"),
        ([MORTGAGE_6], "what if I'm 30 years"),
        ([CAR], "what if I wait 2 years to buy"),
        ([CAR], "what if I keep the car for 10 years"),
        ([CAR], "what if I go from 60 to 36 months"),
        ([MORTGAGE], "what if I sell after 5 years?"),
        ([MORTGAGE_6], "what if rates are 5% in 2 years"),
        ([MORTGAGE_6], "what if rates are 5% for 2 years then go up"),
        ([MORTGAGE_6], "what if it's 5% for 2 years"),
        ([MORTGAGE_6], "what if the rate is 6% for 10 years"),
        ([MORTGAGE_6], "what if I take 6 months of maternity leave"),
        ([STUDENT], "what if I get 2 years of deferment"),
        ([CAR_PLAIN], "what if I get 3 months free"),
        ([CAR_PLAIN], "what if I get 0% for 12 months"),
        ([CAR_PLAIN], "what if I save for 2 years"),
        ([CARD], "what about 20 years"),
        # A percent that is not the loan's rate.
        ([CAR_PLAIN], "what if sales tax is 7%"),
        ([MORTGAGE_6], "what if property tax is 1.2%"),
        ([SAVINGS], "what if I get a 5% match from my employer"),
        ([CARD], "what if I get 2% back"),
        ([MORTGAGE_6], "what if I'm at 80% LTV"),
        ([CAR_PLAIN], "what if it's at 85% of msrp"),
        ([CAR], "what if the rate is 6% down from 7.16%"),
        ([MORTGAGE_6], "what if it's 20%"),
        ([CAR], "what if rates drop 1% next year?"),
        ([CAR], "lol 100%"),
        ([CAR], "is 7% a good rate?"),
        # A bare percent counts only alone; beside another change it needs its rate words.
        ([CAR_PLAIN], "what about 48 months instead of 60 and 5% instead of 7%"),
        # The third review: a card payment as a percent, "new" beside a rate or price.
        ([CARD], "what if my payment is 3%"),
        ([CARD], "what if the monthly payment was 4%"),
        ([CARD], "what if I only do 3%"),
        ([USED], "what if the new rate is 9%"),
        ([USED], "what if the new price is 12k"),
        # A price, an amount, a down payment, a payment, a deposit or a kind: the model's.
        ([CAR], "what if I put 5000 down?"),
        ([CAR], "what if I put 20% down?"),
        ([CAR], "what if the car was $18,000?"),
        ([CAR], "what if I only borrow 8000?"),
        ([CAR, "what if i only do 3 years instead"], "and with 5000 down?"),
        ([MORTGAGE_6], "what about 400k?"),
        ([CARD], "what if I pay 300 a month instead?"),
        ([CARD], "what if I owe 8000"),
        ([CARD], "what if I pay 1000 now"),
        ([SAVINGS], "what if I save 300 a month instead"),
        ([SAVINGS], "what if I start with 5000"),
        ([CAR], "what if it was a used car?"),
        ([USED], "what if it was new instead"),
        ([BIRR], "what if it was $400k"),
        # The third review's lines.
        ([USED_8], "what about a 2019 model?"),
        ([USED_8], "what if it's a 2015"),
        ([MORTGAGE_SHARE], "what if I put 20% down, so 80k"),
        ([USED], "what if I put 25% down, 3500"),
        ([MORTGAGE_SHARE], "what about 3.5 down?"),
        ([CAR_PLAIN], "10 down?"),
        ([SAVINGS_1K], "what if I make 3000 a month"),
        ([CARD], "what if I'm paid 3000 a month"),
        # The earlier reviews' lines.
        ([CAR_PLAIN], "what if I pay 400 instead?"),
        ([CAR_PLAIN], "what if the trade-in is worth 4000"),
        ([CAR_PLAIN], "what if it's 40k miles"),
        ([MORTGAGE_6], "what if the house is 1500 sq ft"),
        ([CAR_PLAIN], "what about 36m"),
        ([CAR_PLAIN], "and with 60k salary?"),
    ],
)
def test_a_line_that_changes_no_term_or_rate_is_none(earlier: list[str], line: str) -> None:
    assert follow_up_request(line, earlier) is None


def test_the_kind_stays_the_requests_own() -> None:
    request = follow_up_request("hmm what if i only do 3 years instead", [USED])
    assert request is not None and request.variant == "used"


def test_a_first_ask_is_no_follow_up() -> None:
    """The reader of a request alone stays as it was; the follow-up is the turn's to ask."""
    assert follow_up_request(CAR, []) is None
    first = read_money_request(CAR)
    assert first is not None and first.changed == ()


@pytest.mark.parametrize(
    ("line", "rate", "term"),
    [
        ("at 6%", 6, None),
        ("6% apr", 6, None),
        ("6% interest", 6, None),
        ("the rate is 6%", 6, None),
        ("what about 6.5%?", 6.5, None),
        ("over 4 years", None, (4, "years")),
        ("a 15 year mortgage at 5.5%", 5.5, (15, "year")),
    ],
)
def test_the_grammar_reads_a_term_and_a_rate(
    line: str, rate: float | None, term: tuple[float, str] | None
) -> None:
    change = read_change(line)
    assert change is not None and (change.rate, change.term) == (rate, term)
