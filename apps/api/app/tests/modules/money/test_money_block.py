"""The block the model reads: numbers to copy, what was assumed, what the app adds."""

from __future__ import annotations

from app.modules.money.block import (
    MONEY_RATE_MISSING,
    MONEY_RATES_FOUND,
    MONEY_RATES_MISSING,
    MONEY_REPLY_RULES,
    money_block,
)
from app.modules.money.catalog import product
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import work
from app.tests.modules.money.money_support import average


def test_the_block_gives_the_worked_numbers_and_the_assumption() -> None:
    request = MoneyRequest(product("mortgage"), {"amount": 300000, "rate": 1}, "USD")
    block = money_block(request, work(request, None), None)
    assert "Currency: USD." in block
    assert "amount 300,000; yearly rate 1%; term in years 30 (assumed" in block
    assert "monthly payment 964.92; total interest 47,370.68; total paid 347,370.68" in block
    assert MONEY_REPLY_RULES in block


def test_the_block_asks_for_a_rate_when_there_is_none() -> None:
    request = MoneyRequest(product("mortgage"), {"amount": 300000})
    assert MONEY_RATE_MISSING in money_block(request, None, None)


def test_a_payment_that_never_clears_the_card_is_said_plainly() -> None:
    request = MoneyRequest(product("card"), {"balance": 5000, "apr": 24, "payment": 100})
    block = money_block(request, work(request, None), None)
    assert "months to pay off: never" in block


def test_a_rates_question_gets_the_checked_average_or_none() -> None:
    request = MoneyRequest(product("mortgage"), {}, rates_only=True)
    found = money_block(request, None, average())
    assert "6.27% as of Oct 16, 2026" in found and MONEY_RATES_FOUND in found
    assert MONEY_RATES_MISSING in money_block(request, None, None)
