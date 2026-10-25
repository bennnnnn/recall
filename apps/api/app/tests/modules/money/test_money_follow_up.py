"""A line that changes the chat's last money request, and the look-alikes that change none.

Live (2026-10-25): "hmm what if i only do 3 years instead" after a used-car loan got no
card, and the model's own arithmetic was off by dollars. Two reviews of the fix (same
day): a percent or a sum beside other words became the rate or the price ("what if sales
tax is 7%", "what if I pay 400 instead?", "it's 40k miles", "I get a 5% match from my
employer", "rates are 5% for 2 years then go up"). The reader is now a positive grammar
(``change_line``): a line with any word it does not place is no follow-up.
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
CAR_PLAIN = "car loan 20000 at 7% for 5 years, what's the monthly payment"
MORTGAGE = "what is my mortgage for 300k dollars house if mr rate is 1 percent"
MORTGAGE_6 = "mortgage of 300k at 6% for 30 years"
MORTGAGE_SHARE = "mortgage on a 500k house with 20% down at 6.5%"
BIRR = "mortgage of 3 million birr at 15% for 20 years"
STUDENT = "student loan of 30000 at 5.5% for 10 years"
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
        # The percent or the sum is the rate or the price by its own words.
        ([CAR], "7%", {"rate": 7}, ("rate",)),
        ([CAR], "what if it's 5%", {"rate": 5}, ("rate",)),
        ([CAR], "what if I get 4.5% apr instead", {"rate": 4.5}, ("rate",)),
        ([CAR], "what if the interest rate was 6%", {"rate": 6}, ("rate",)),
        ([CAR], "what if it's 2 years?", {"months": 24}, ("months",)),
        ([CAR], "what if I pay 5000 upfront", {"amount": 9000}, ("down",)),
        ([CAR_PLAIN], "what if I pay 5000 cash upfront", {"amount": 15000}, ("down",)),
        ([CAR_PLAIN], "20k", {"amount": 20000}, ("amount",)),
        ([MORTGAGE_6], "what about 400k?", {"amount": 400000}, ("amount",)),
        ([MORTGAGE_6], "what if the house was 400k", {"amount": 400000}, ("amount",)),
        ([USED], "what if I bought a new car for 30000 instead", {"amount": 27000}, ("amount", "variant")),
        ([CARD], "what if the balance was 8000", {"balance": 8000}, ("balance",)),
        ([CARD], "what if I owe 8000", {"balance": 8000}, ("balance",)),
        # The reviewer's lines the grammar reads whole.
        ([CAR], "same but 5000 down", {"amount": 9000}, ("down",)),
        ([CAR], "but at 5%?", {"rate": 5}, ("rate",)),
        ([CAR_PLAIN], "what if it was 25k and I put 5k down", {"amount": 20000}, ("down", "amount")),
        ([CAR_PLAIN], "what if I do 4 years at 5% with 2000 down", {"amount": 18000, "months": 48, "rate": 5}, ("rate", "months", "down")),
        ([CAR_PLAIN], "what about 48 months instead of 60 and 5% instead of 7%", {"months": 48, "rate": 5}, ("rate", "months")),
        ([CAR_PLAIN], "what if I buy it used at 9%", {"rate": 9}, ("rate", "variant")),
        ([MORTGAGE_6], "what if I get 5.5% on a 15 year", {"rate": 5.5, "years": 15}, ("rate", "years")),
        ([MORTGAGE_6], "what about 180 months", {"years": 15}, ("years",)),
        ([MORTGAGE_6], "what if the down payment is 60k", {"amount": 240000}, ("down",)),
        ([MORTGAGE_6], "what if I finance 250k over 15 years", {"amount": 250000, "years": 15}, ("years", "amount")),
        ([CARD], "what if I pay $300/mo", {"payment": 300}, ("payment",)),
        ([CARD], "what about 15% apr", {"apr": 15}, ("apr",)),
        ([SAVINGS], "what if I start with 10k and save 300 a month", {"start": 10000, "deposit": 300}, ("deposit", "start")),
        ([SAVINGS], "what if I save for 20 years", {"years": 20}, ("years",)),
        ([STUDENT], "what if I borrow 40k", {"amount": 40000}, ("amount",)),
        ([BIRR], "what about 4 million birr?", {"amount": 4_000_000}, ("amount",)),
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
        ([CAR], "what if I go from 60 to 36 months"),
        # A percent that is not the rate: the reviewer's lines.
        ([MORTGAGE_6], "what if property tax is 1.2%"),
        ([MORTGAGE_6], "and property tax of 1.2%?"),
        ([MORTGAGE_6], "what if PMI is 0.5%"),
        ([MORTGAGE_6], "what if the house appreciates 4% a year"),
        ([MORTGAGE_6], "with 3% inflation?"),
        ([CAR_PLAIN], "what if sales tax is 7%"),
        ([CAR_PLAIN], "with 7% sales tax?"),
        ([CAR_PLAIN], "what if the tax is 8%"),
        ([CAR_PLAIN], "what if I get a 3% raise"),
        ([CAR_PLAIN], "what if the dealer gives me 2% cash back"),
        ([SAVINGS], "what if inflation is 3%"),
        ([SAVINGS], "what about with 10% returns"),
        ([CAR_PLAIN], "what if my credit card is at 25%"),
        # A percent with "in 2 years" is when, not the term.
        ([MORTGAGE_6], "what if I refinance at 5% in 2 years"),
        ([MORTGAGE_6], "what if rates are 5% in 2 years"),
        ([CAR_PLAIN], "what if rates are 5% in 2 years"),
        ([CAR_PLAIN], "what if I sell it in 2 years"),
        # A sum that is not the price: paid, sold, saved, earned, a model year.
        ([CAR_PLAIN], "what if I pay 400 instead?"),
        ([CAR_PLAIN], "what if I only pay 450?"),
        ([MORTGAGE_6], "what if I pay 2000"),
        ([CAR_PLAIN], "what if the trade-in is worth 4000"),
        ([CAR_PLAIN], "what if I sell my old car for 4000"),
        ([CAR_PLAIN], "what if I pay 150 for insurance"),
        ([CAR_PLAIN], "what if gas costs 200"),
        ([CAR_PLAIN], "and with 60k salary?"),
        ([CAR_PLAIN], "what about with 2 kids"),
        ([CAR_PLAIN], "what if I get a 2022 car instead"),
        ([CAR_PLAIN], "what if I trade in my 2015 car"),
        ([CAR_PLAIN], "what if I paid 5000 cash"),
        ([CAR_PLAIN], "what if I had 5000 saved"),
        ([MORTGAGE_6], "what if I rent it for 2000"),
        # A savings sum or a card sum with no word for its role could be either input.
        ([SAVINGS], "what if I save 300 instead"),
        ([SAVINGS], "what if I invest 5000"),
        ([CARD], "8000?"),
        # The second review: a percent beside words that are not the rate's.
        ([SAVINGS], "what if I get a 5% match from my employer"),
        ([CARD], "what if I get 2% back"),
        ([CARD], "what if I'm at 30% utilization"),
        ([MORTGAGE_6], "what if I'm at 80% LTV"),
        ([MORTGAGE_6], "what if we're at 36% DTI"),
        ([MORTGAGE_6], "what if I get 20% equity"),
        ([CAR_PLAIN], "what if it's at 85% of msrp"),
        ([MORTGAGE_6], "what if I get 5% down"),
        ([CAR], "what if the rate is 6% down from 7.16%"),
        # A sum beside a unit that is not money.
        ([CAR_PLAIN], "what if it's 40k miles"),
        ([CAR_PLAIN], "what if the car is 50k miles"),
        ([MORTGAGE_6], "what if the house is 1500 sq ft"),
        ([MORTGAGE_6], "what if the house is 30 minutes from work"),
        ([MORTGAGE_6], "what if the home is 3 bedrooms"),
        # A length of time that is not the loan's, or one no slider of it reaches.
        ([MORTGAGE_6], "what if rates are 5% for 2 years then go up"),
        ([MORTGAGE_6], "what if it's 5% for 2 years"),
        ([MORTGAGE_6], "what if the rate is 4% for 3 years and then adjusts"),
        ([MORTGAGE_6], "what if I take 6 months of maternity leave"),
        ([STUDENT], "what if I get 2 years of deferment"),
        ([STUDENT], "what if I go 6 months without paying"),
        ([CAR_PLAIN], "what if I get 3 months free"),
        ([CAR_PLAIN], "what if I get 0.9% for 2 years then 7%"),
        ([MORTGAGE_6], "what if it's 20%"),
        ([CAR_PLAIN], "what about 36m"),
        ([MORTGAGE_6], "what about 2000?"),
        ([CAR_PLAIN], "what if I save for 2 years"),
        # A card payment made once, not each month.
        ([CARD], "what if I pay 1000 now"),
        ([CARD], "what if I pay 2000 today"),
        ([CARD], "what if I paid 1500 right away"),
        # A currency the request is not in.
        ([BIRR], "what if it was $400k"),
        ([CAR_PLAIN], "what if it was 2 million yen"),
        ([CAR_PLAIN], "what if it was 20000 euros"),
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


def test_a_share_put_down_stays_a_share_of_a_new_price() -> None:
    """ "500k house with 20% down", then "a 600k house": 20% of 600k down, so 480,000."""
    request = follow_up_request("what about a 600k house?", [MORTGAGE_SHARE])
    assert request is not None and request.down_share == 20
    assert (request.values["amount"], request.down) == (480_000, 120_000)
    fixed = follow_up_request("what if I put 50k down", [MORTGAGE_SHARE])
    assert fixed is not None and fixed.down_share is None and fixed.values["amount"] == 450_000


def test_a_currency_must_be_the_requests_own() -> None:
    """A request that named none is in the user's place's currency."""
    assert follow_up_request("what if it was $25k", [CAR_PLAIN]) is not None
    assert follow_up_request("what if it was $25k", [CAR_PLAIN], "Addis Ababa, Ethiopia") is None
    assert follow_up_request("what if it was 25k birr", [CAR_PLAIN], "Addis Ababa, Ethiopia")


def test_a_first_ask_is_no_follow_up() -> None:
    """The reader of a request alone stays as it was; the follow-up is the turn's to ask."""
    assert follow_up_request(CAR, []) is None
    first = read_money_request(CAR)
    assert first is not None and first.changed == () and first.down == 3000


@pytest.mark.parametrize(
    ("earlier", "line", "variant"),
    [
        ([USED], "what if I bought a new car for 30000 instead", ""),
        ([USED], "what if it was new instead", ""),
        ([CAR], "what if it was a used car?", "used"),
        ([USED], "hmm what if i only do 3 years instead", "used"),
    ],
)
def test_a_follow_up_can_change_the_kind_either_way(
    earlier: list[str], line: str, variant: str
) -> None:
    request = follow_up_request(line, earlier)
    assert request is not None and request.variant == variant


@pytest.mark.parametrize(
    "line",
    ["what if I get a new job", "what if I bought a new car, not a used one"],
)
def test_new_beside_nothing_bought_or_beside_used_is_no_kind(line: str) -> None:
    assert follow_up_request(line, [USED]) is None
