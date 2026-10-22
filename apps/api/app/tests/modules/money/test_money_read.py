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
