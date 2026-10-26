"""A loan told over two lines: what the user is buying, then only its amount and rate.

Live (2026-10-25): "I am planing to buy a car", the reply asking new or used and the
budget, then "20k with 6 percent". Neither line read as a request, no card was built, and
the model's own interest was $1,930 where 20k at 6% over 36 months is $1,904.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.money import service
from app.modules.money.follow_up import follow_up_request
from app.modules.money.purchase import purchase_request
from app.modules.money.rates import MarketRate

CAR = "I am planing to buy a car"
HOUSE = "House buying for 400k"


@pytest.mark.parametrize(
    ("before", "line", "product", "values"),
    [
        # The live lines.
        (CAR, "20k with 6 percent", "car", {"amount": 20000, "rate": 6}),
        (HOUSE, "60k down at 6 percent", "mortgage", {"amount": 340000, "rate": 6}),
        # Other ways to say what is being bought.
        ("I'm thinking of buying a used car", "14000 at 9%", "car", {"amount": 14000, "rate": 9}),
        ("we want to buy a truck next month", "$30k at 7% apr", "car", {"amount": 30000, "rate": 7}),
        ("buying a house", "350k at 6.5%", "mortgage", {"amount": 350000, "rate": 6.5}),
        ("I'm going to buy a home.", "300,000 at 6% interest", "mortgage", {"amount": 300000}),
        # A term, in the product's own unit.
        (CAR, "20k at 6% for 3 years", "car", {"months": 36}),
        ("buying a condo", "200k at 6% over 15 years", "mortgage", {"years": 15}),
        # A price named: only an amount said to be down is read, and it comes off the price.
        ("buying a house for 400k", "down payment of 60k at 6%", "mortgage", {"amount": 340000}),
        ("we're buying a 400k house", "with 80k down", "mortgage", {"amount": 320000}),
        ("I'm looking to buy a 30k car", "I can put 5k down at 7%", "car", {"amount": 25000}),
        ("buying a 30,000 car", "5k down", "car", {"amount": 25000}),
        # A model year describes the car; it is not its price.
        ("I want to buy a 2018 truck", "20k at 7%", "car", {"amount": 20000, "rate": 7}),
        ("getting a used 2016 car", "12k at 8%", "car", {"amount": 12000}),
        ("I want to buy a 2018 truck for 15k", "$500 down", "car", {"amount": 14500}),
        ("I want to finance my car", "20k at 6%", "car", {"amount": 20000}),
    ],
)  # fmt: skip
def test_a_purchase_then_an_amount_and_rate_is_that_products_loan(
    before: str, line: str, product: str, values: dict[str, float]
) -> None:
    request = purchase_request(line, (before,))
    assert request is not None and request.product.key == product
    assert {name: request.values.get(name) for name in values} == values


def test_the_kind_of_car_bought_is_the_requests() -> None:
    request = purchase_request("14000 at 9%", ("I'm thinking of buying a used car",))
    assert request is not None and request.variant == "used"


def test_a_currency_named_is_kept() -> None:
    request = purchase_request("20,000 dollars at 6%", (CAR,))
    assert request is not None and request.currency == "USD"


@pytest.mark.parametrize(
    ("before", "line"),
    [
        # Not a line about buying one.
        ("I bought a car last week.", "20k with 6 percent was a good deal?"),
        ("I bought a car last week.", "20k with 6 percent"),
        ("buy a house in minecraft", "20k with 6 percent"),
        ("buying a car for my son", "20k with 6 percent"),
        ("I'm planning to buy a car. What should I check first?", "20k at 6%"),
        ("my car does 20k miles a year", "20k at 6%"),
        ("I want to buy a car loan calculator app", "20k at 6%"),
        ("what's the best savings account?", "20k at 6%"),
        # "Get my car" is one already theirs.
        ("I want to get my car", "20k at 6%"),
        ("I need to get my car", "20k at 6%"),
        ("we need to get our house", "300k at 6%"),
        # A model year is not a price, so a down payment has nothing to come off.
        ("I'm buying a 2021 suv", "$2,000 down"),
        ("buying a 2015 car", "with $1,000 down at 8%"),
        ("I want to buy a 2018 truck", "$500 down at 7%"),
        ("I want to buy a 1999 car", "1500 down at 6%"),
        # A bare number before the car may be either.
        ("buying a 1500 car", "500 down"),
        # Not only an amount and a rate.
        (CAR, "20k steps with 6 percent incline"),
        (CAR, "my car does 20k miles a year"),
        (CAR, "20k with 6 percent growth for 3 years"),
        (CAR, "I make 60k at 6 percent raise"),
        (CAR, "my salary is 60k with 6 percent bonus"),
        (CAR, "20k with 6 percent was a good deal?"),
        (CAR, "20 with 6 percent"),
        (CAR, "20k"),
        (CAR, "6 percent"),
        # A down payment with no price before it: the 20k may have been the price or the loan.
        (CAR, "Down payment 3k"),
        (CAR, "3k down at 6%"),
        # A price named: a bare amount may be the loan or the down payment.
        (HOUSE, "60k at 6 percent"),
        (HOUSE, "at 6 percent"),
        # A down payment that is not less than the price, or in another currency.
        (HOUSE, "400k down at 6%"),
        ("buying a house for €400k", "$60k down at 6%"),
    ],
)
def test_anything_else_is_no_purchase_loan(before: str, line: str) -> None:
    assert purchase_request(line, (before,)) is None


def test_the_line_before_counts_only_as_one_part() -> None:
    assert purchase_request("20k at 6%", ()) is None
    assert purchase_request("20k at 6%", ("remind me at 9", CAR)) is None


def test_a_what_if_changes_the_loan_told_over_two_lines() -> None:
    request = follow_up_request("what if 3 years instead", [CAR, "20k with 6 percent"])
    assert request is not None and request.product.key == "car"
    assert request.values == {"amount": 20000, "rate": 6, "months": 36}
    assert request.changed == ("months",)


def test_a_down_payment_after_the_loan_stays_with_the_model() -> None:
    assert follow_up_request("Down payment 3k", [CAR, "20k with 6 percent"]) is None


async def test_the_live_car_loan_is_worked_by_the_server(monkeypatch) -> None:
    calls: list[tuple] = []

    async def current_average(product, term, country, settings, redis, **_: Any):
        calls.append((product.key, term))
        await asyncio.sleep(0)
        return None

    monkeypatch.setattr(service, "current_average", current_average)
    turn = await service.prepare_money_turn(
        "20k at 6% for 36 months", Settings(), None, user=None, location=None, earlier=[(CAR,)]
    )
    assert turn is not None and turn.worked is not None
    assert round(turn.worked.outputs["interest"] or 0) == 1904
    assert round(turn.worked.outputs["payment"] or 0, 2) == 608.44
    reply = await service.finish_money_reply(turn, "About $608.44 a month.", Settings())
    assert "```calculator\n" in reply
    assert calls == [("car", 36)]


async def test_the_ambiguous_house_line_is_no_money_turn(monkeypatch) -> None:
    async def current_average(*_: Any, **__: Any) -> MarketRate | None:
        raise AssertionError("no lookup for a line the server leaves to the model")

    monkeypatch.setattr(service, "current_average", current_average)
    turn = await service.prepare_money_turn(
        "60k at 6 percent", Settings(), None, user=None, location=None, earlier=[(HOUSE,)]
    )
    assert turn is None
