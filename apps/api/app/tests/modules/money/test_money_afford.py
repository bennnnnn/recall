"""What an income can borrow, by the common 28/36 rule: worked by the server, carded."""

from __future__ import annotations

import json

import pytest

from app.modules.money.block import money_block
from app.modules.money.catalog import product
from app.modules.money.fence import calculator_fence
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import Worked, work


def _worked(**values: float) -> Worked:
    worked = work(MoneyRequest(product("afford"), dict(values), "USD"), None)
    assert worked is not None
    return worked


@pytest.mark.parametrize(
    ("values", "payment", "loan"),
    [
        # 28% of 200k a year is 4,666.67 a month; at 6% over 30 years it borrows 778,360.87.
        ({"income": 200000, "debts": 0, "rate": 6}, 4666.67, 778360.87),
        # Other debts leave 36% less them: 3,000 - 2,500 = 500 a month, over 3 years.
        ({"income": 100000, "debts": 2500, "rate": 6, "years": 3}, 500.0, 16435.51),
        # Debts above 36% leave no room at all, never a negative loan.
        ({"income": 50000, "debts": 2000, "rate": 6}, 0.0, 0.0),
        # At 0% the loan is the payments' sum.
        ({"income": 120000, "debts": 0, "rate": 0, "years": 10}, 2800.0, 336000.0),
    ],
)
def test_the_most_an_income_borrows(values: dict, payment: float, loan: float) -> None:
    worked = _worked(**values)
    assert round(worked.outputs["most_payment"] or 0, 2) == payment
    assert round(worked.outputs["most_loan"] or 0, 2) == loan


def test_unsaid_debts_and_term_are_assumed() -> None:
    worked = _worked(income=200000, rate=6)
    assert worked.assumed == ("debts", "years") and worked.values["years"] == 30


def test_the_card_is_built_and_checked() -> None:
    fence = calculator_fence(_worked(income=200000, debts=0, rate=6), None, "USD")
    assert fence is not None and fence.startswith("```calculator\n")
    spec = json.loads(fence.split("\n", 1)[1].rsplit("```", 1)[0])
    assert spec["product"] == "afford" and spec["title_key"] == "money.title.afford"
    assert [item["name"] for item in spec["controls"]] == ["income", "debts", "rate", "years"]
    assert spec["readouts"][0]["name"] == "most_loan" and spec["readouts"][0]["primary"]


def test_the_block_names_the_rule_and_the_price_asked() -> None:
    request = MoneyRequest(
        product("afford"), {"income": 200000, "debts": 0, "rate": 6}, "USD", price=1e6
    )
    block = money_block(request, work(request, None), None)
    assert "the most the income can borrow 778,360.87" in block
    assert "28/36 rule" in block and "costs 1,000,000" in block
