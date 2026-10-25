"""Which messages are money requests, and the numbers read out of them."""

from __future__ import annotations

import pytest

from app.modules.money.read import read_money_request


@pytest.mark.parametrize(
    ("text", "product", "values", "currency"),
    [
        (
            "what is my mortgage for 300k dollars house if mr rate is 1 percent",
            "mortgage",
            {"amount": 300000, "rate": 1},
            "USD",
        ),
        ("car loan 30000 at 6% for 5 years monthly payment", "car", {"amount": 30000, "rate": 6, "months": 60}, ""),
        (
            "what would my car payment be on a $32,000 car at 7.5% APR for 72 months",
            "car",
            {"amount": 32000, "rate": 7.5, "months": 72},
            "USD",
        ),
        (
            "a 400k house with 80k down at 6.5% for 15 years, what is the monthly payment",
            "mortgage",
            {"amount": 320000, "rate": 6.5, "years": 15},
            "",
        ),
        (
            "I owe 5000 on my credit card at 22% apr and pay 200 a month, how long to pay off",
            "card",
            {"balance": 5000, "apr": 22, "payment": 200},
            "",
        ),
        (
            "if I save 200 a month at 4.5% for 10 years how much will I have",
            "savings",
            {"deposit": 200, "rate": 4.5, "years": 10},
            "",
        ),
        (
            "I have $10k in savings at 4% and add $500 a month for 20 years",
            "savings",
            {"start": 10000, "deposit": 500, "rate": 4, "years": 20},
            "USD",
        ),
        ("student loan of 40,000 at 5.5%", "student", {"amount": 40000, "rate": 5.5}, ""),
        (
            "borrow 25000 for a personal loan at 11% over 3 years",
            "personal",
            {"amount": 25000, "rate": 11, "months": 36},
            "",
        ),
        (
            "mortgage of 2 million birr at 18% for 20 years",
            "mortgage",
            {"amount": 2_000_000, "rate": 18, "years": 20},
            "ETB",
        ),
        ("monthly payment on a 250000 mortgage", "mortgage", {"amount": 250000}, ""),
    ],
)  # fmt: skip
def test_read_money_request_reads_the_numbers(
    text: str, product: str, values: dict[str, float], currency: str
) -> None:
    request = read_money_request(text)
    assert request is not None
    assert request.product.key == product
    assert request.values == values
    assert request.currency == currency
    assert not request.rates_only


@pytest.mark.parametrize(
    ("text", "product"),
    [
        ("what are mortgage rates right now", "mortgage"),
        ("what's the average credit card APR these days?", "card"),
        ("current car loan rates", "car"),
    ],
)
def test_read_money_request_knows_a_rates_question(text: str, product: str) -> None:
    request = read_money_request(text)
    assert request is not None and request.rates_only and request.product.key == product


@pytest.mark.parametrize(
    "text",
    [
        "I'm interested in cars",
        "rate my essay out of 10",
        "who is the principal of my school",
        "credit card design ideas",
        "my card was declined at the store",
        "pay attention to the details",
        "the interest of the story fades in act 3",
        "savings on groceries tips",
        "how much should I save for a house",
        "mortgage rates in 2026",
        "compound interest on 1000 at 5% for 3 years",
        "simple interest on $1200 at 5% per year for 4 years",
        "$5000 invested at 4% interest compounded annually for 3 years",
        "my house is 20 years old",
        "I drove my car 300 miles",
        "",
    ],
)
def test_read_money_request_leaves_other_messages(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        # Live (2026-10-25): this got the new-car average.
        (
            "i'm thinking of buying a used car for 14000, i can put 3000 down. what would my "
            "monthly payment be over 5 years?",
            "used",
        ),
        ("pre-owned car loan 18000 at 8% for 60 months", "used"),
        ("certified pre-owned car, 25k car loan over 72 months, payment?", "used"),
        ("second-hand car for 9000 with a car loan, payment over 4 years", "used"),
        ("used-car loan of 12000 at 9%", "used"),
        # "A used car" someone used to have, sold or trades in is not the one financed.
        ("I used to have a used car, now a 20000 car loan at 6% for 5 years?", ""),
        ("trading in my used car, new car loan 30000", ""),
        ("car loan 30000 for a new car, I don't want a used one", ""),
        ("car loan 30000 for a brand new car instead of used", ""),
        ("I sold my used car, now a car loan of 30000 for a new one", ""),
        ("car loan of 30000, it's for my wife's used Honda", ""),
        ("car loan 30000 at 6%, the used car market is crazy", ""),
        ("car loan 25000 at 6%, what rate is used", ""),
        ("used car payment on 15k at 9%", "used"),
        ("pre-owned truck loan 28000 at 8.5% for 6 years", "used"),
        # "Used" as a verb names no kind.
        ("I used a calculator and got 400 a month on a car loan of 20000 at 6%", ""),
        ("I'm used to paying 300 a month, what would a 20000 car loan cost over 5 years", ""),
        ("the car I used to have cost 15000; what's the payment on a 25000 car loan", ""),
        ("what would I have used for a 20000 car loan over 5 years", ""),
        ("what rate is used for a 20000 car loan over 5 years", ""),
        ("new car loan 30000 at 6% for 5 years", ""),
        ("car loan 30000 at 6% for 5 years", ""),
        # A product with no kinds priced apart.
        ("used furniture loan of 3000 at 9%", ""),
    ],
)
def test_read_money_request_reads_the_kind(text: str, variant: str) -> None:
    request = read_money_request(text)
    assert request is not None and request.variant == variant


def test_a_rates_question_keeps_the_kind() -> None:
    request = read_money_request("current used car loan rates")
    assert request is not None and request.rates_only and request.variant == "used"


@pytest.mark.parametrize(
    ("text", "values"),
    [
        # "3 years ago" says when, not the term: the default stands.
        ("mortgage of 300k at 6%, I bought the house 3 years ago", {"amount": 300000, "rate": 6}),
        ("mortgage of 300k at 6% for 15 years, I'll sell after 5 years", {"amount": 300000, "rate": 6, "years": 15}),
        # "20% down" is a share of the price, not the rate.
        ("a 400k house with 20% down at 6.5% for 30 years", {"amount": 320000, "rate": 6.5, "years": 30}),
        ("car loan for 14000, I can put down 3000, at 7% for 5 years", {"amount": 11000, "rate": 7, "months": 60}),
        ("car loan 22000 at 5.9% 72 months, 4000 cash down", {"amount": 18000, "rate": 5.9, "months": 72}),
        ("balance was 3000 on my credit card at 25% paying 100 a month", {"balance": 3000, "apr": 25, "payment": 100}),
        # The second review: these read as the parent read them (an "upfront fee" is no
        # down payment, "6% down from 7%" no share, "I'm 2 down on payments" no sum).
        ("mortgage 300k, rate is 6% down from 7%", {"amount": 300000, "rate": 6}),
        ("personal loan of 20000 at 10% with a 500 upfront fee", {"amount": 20000, "rate": 10}),
        ("my mortgage is 200k at 6%, rates went down 1 point, should I refinance", {"amount": 200000, "rate": 6}),
        ("car loan 20000 at 7% for 5 years, I'm 2 down on payments", {"amount": 20000, "rate": 7, "months": 60}),
        ("student loan 30000 at 5% repaid after 10 years", {"amount": 30000, "rate": 5, "years": 10}),
        # A year before a vehicle is its model year beside a price; alone, it is the price.
        ("loan for a 2020 car of 15000 at 6%", {"amount": 15000, "rate": 6}),
        ("a 2000 car with a loan at 10% for 12 months", {"amount": 2000, "rate": 10, "years": 1}),
        # A percent after an earlier sum put down is the rate (the first fix took it as a
        # share of the price: review, 2026-10-25).
        ("car loan 25000 with 5000 down 6.9% apr 60 months", {"amount": 20000, "rate": 6.9, "months": 60}),
        ("mortgage on a 400k house, 50k down 6.5% for 30 years", {"amount": 350000, "rate": 6.5, "years": 30}),
        ("mortgage 500k 100k down payment 6.25% 30 year", {"amount": 400000, "rate": 6.25, "years": 30}),
        ("car loan 20000, I can put 2000 down 8% 4 years", {"amount": 18000, "rate": 8, "months": 48}),
        ("300k house with 60k down 6% 30 yr", {"amount": 240000, "rate": 6, "years": 30}),
        ("down payment 20% on a 350k home at 6.75% for 30 years", {"amount": 280000, "rate": 6.75, "years": 30}),
        # "Went down 1% to 5.5%": the rate is where it went.
        ("my mortgage is 200k, rate went down 1% to 5.5%", {"amount": 200000, "rate": 5.5}),
        # "Paid off after" and "will last" give the term; "the past 3 years" does not.
        ("a 300k mortgage at 6% paid off after 15 years", {"amount": 300000, "rate": 6, "years": 15}),
        ("car loan 20000 at 6%, paid off after 3 years", {"amount": 20000, "rate": 6, "months": 36}),
        ("a car loan of 20000 at 6% that will last 5 years", {"amount": 20000, "rate": 6, "months": 60}),
        # Unsure readings stay the parent reader's: "over the past 3 years", "after 2 years".
        ("car loan 15000 at 6% over the past 3 years", {"amount": 15000, "rate": 6, "months": 36}),
        ("loan 10000 at 5% after 2 years", {"amount": 10000, "rate": 5, "years": 2}),
        # The fourth review: a rate said as a rate keeps it ahead of "down ..." after it.
        ("car loan 25000 at 7% down payment of 5000 for 60 months", {"amount": 20000, "rate": 7, "months": 60}),
        ("mortgage 400k at 6.5% down payment 80k 30 years", {"amount": 320000, "rate": 6.5, "years": 30}),
        ("mortgage 300k at 6.5% down 0.25% from last month", {"amount": 300000, "rate": 6.5}),
        ("car loan 20000, rate is 7% down 1% from last year", {"amount": 20000, "rate": 7}),
        ("mortgage 400k 20% down 6.5%", {"amount": 320000, "rate": 6.5}),
        ("mortgage 350k put down 20 percent at 6% for 30 yrs", {"amount": 280000, "rate": 6, "years": 30}),
        ("car loan 18000, 5% down, 7% apr, 5 years", {"amount": 17100, "rate": 7, "months": 60}),
        ("financing a 2000 car at 12% for 12 months with 500 down", {"amount": 1500, "rate": 12, "years": 1}),
        # A model year is no price.
        ("I bought a 2019 car with a car loan of 15000 at 6%", {"amount": 15000, "rate": 6}),
    ],
)  # fmt: skip
def test_read_money_request_reads_what_a_number_is(text: str, values: dict[str, float]) -> None:
    request = read_money_request(text)
    assert request is not None and request.values == values
