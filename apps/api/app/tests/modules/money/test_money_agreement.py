"""A loan reply whose stated payment is not its card's gets the card's figures in a line."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import Settings
from app.modules.money.agreement import card_figures_line
from app.modules.money.block import money_block
from app.modules.money.purchase import purchase_request
from app.modules.money.read import read_money_request
from app.modules.money.service import MoneyTurn, finish_money_reply
from app.modules.money.solve import work

# The live reply (2026-10-26, free model): the card said 340,000 at $2,038.47.
_WRONG = (
    "Here is the breakdown for **$60k** at **6%** over a standard **30-year** term:\n\n"
    "*   **Monthly Payment:** $359.82\n*   **Total Interest Paid:** $71,535.54\n"
    "*   **Total Amount Paid:** $131,535.54"
)
_LINE = "The card's figures: **$2,038.47** a month on a $340,000 loan at 6% over 30 years."


def _house():
    request = purchase_request("60k at 6 percent", ("House buying for 400k",))
    assert request is not None
    request = replace(request, currency="USD")
    worked = work(request, None)
    assert worked is not None
    return request, worked


@pytest.mark.parametrize(
    "reply",
    [
        _WRONG,
        "Your monthly payment is $2,037.97.",
        "That works out to $2,100.00 a month.",
        "You'd pay $2,100/month.",
    ],
)
def test_a_payment_that_is_not_the_cards_gets_the_cards_figures(reply: str) -> None:
    request, worked = _house()

    assert card_figures_line(reply, request, worked) == _LINE


@pytest.mark.parametrize(
    "reply",
    [
        "Your monthly payment is **$2,038.47**.",
        "That comes to $2,038 a month.",
        # Taxes, PMI, other scenarios and the full price (review, 2026-10-26).
        "Your payment is $2,038.47. With taxes and insurance (about $400 a month), plan on "
        "roughly $2,438.",
        "Add PMI only if you put less than 20% down; expect about $150 a month extra.",
        "For comparison, with 20% down ($80,000) the payment would be $1,918.56 a month.",
        "Without a down payment, borrowing the full $400,000 would cost $2,398.20 a month.",
        "With $80,000 down instead, the monthly payment is $1,918.56.",
        # Rounding and ranges.
        "That's about $2,040 a month.",
        "Roughly $2,000 a month.",
        "Expect $2,000–$2,100 a month depending on taxes.",
        "Your payment is $2,038.47 (≈ $2,038.50).",
        "Your payment is $2,038.47 — about $24,462 a year.",
        # The worked formula, ratios and other numbers.
        "Monthly rate: r = 0.06/12 = 0.005. Payment $2,038.47.",
        "$(1.005)^{360} \\approx 6.02$, so the payment is $2,038.47.",
        "Each $1,000 borrowed costs about $6 a month.",
        "That's about 1.5 times your rent. Payment: $2,038.47.",
        "On a 1,800 sq ft home, the payment is $2,038.47.",
        "```python\npayment = 2921.00\n```\nThe payment is $2,038.47.",
        "| Term | Payment |\n|---|---|\n| 30-year | $2,038.47 |\n| 15-year | $2,869.11 |",
        "Over 15 years it would be $2,869.11 a month instead.",
        "If you split it, each of you pays $1,019.24 a month.",
        # No labelled payment at all.
        "Here are your numbers. The card below lets you try other terms.",
    ],
)
def test_other_replies_get_nothing(reply: str) -> None:
    request, worked = _house()

    assert card_figures_line(reply, request, worked) is None


@pytest.mark.parametrize(
    ("ask", "reply"),
    [
        (
            "Can I afford a 300k mortgage at 6.5% on a 90k salary?",
            "Your monthly payment is $1,896.20. Your gross monthly income is $7,500, and 28% "
            "of that is $2,100, so yes, it fits.",
        ),
        (
            "20000 car loan at 7% for 60 months, plus insurance of 150 a month",
            "Payment $396.02, plus $150 insurance = $546.02 a month.",
        ),
        ("car loan 17000 at 6% for 60 months", "You'd borrow $17,000 at **$328.66** a month."),
    ],
)
def test_a_reply_that_answers_its_own_request_gets_nothing(ask: str, reply: str) -> None:
    request = read_money_request(ask)
    assert request is not None
    worked = work(request, None)
    assert worked is not None

    assert card_figures_line(reply, request, worked) is None


def test_card_and_savings_turns_get_nothing() -> None:
    for ask in (
        "credit card balance 5000 at 22% apr paying 200 a month",
        "save 500 a month at 5% for 20 years",
    ):
        request = read_money_request(ask)
        assert request is not None
        worked = work(request, None)
        assert worked is not None
        assert card_figures_line("You'll pay $999.99 a month.", request, worked) is None


def _turn(*, multi: bool = False) -> MoneyTurn:
    request, worked = _house()
    return MoneyTurn(request, worked, money_block(request, worked, None), None, None, multi=multi)


async def test_the_line_goes_above_the_note_and_the_reply_is_kept() -> None:
    settings = Settings()

    english = await finish_money_reply(_turn(), _WRONG, settings)
    other = await finish_money_reply(_turn(), _WRONG, settings, english=False)
    multi = await finish_money_reply(_turn(multi=True), _WRONG, settings)

    assert english.startswith(_WRONG + "\n\n" + _LINE + "\n\n**Read as:**")
    assert "```calculator" in english
    assert _LINE not in other and _LINE not in multi
    assert other.startswith(_WRONG) and multi.startswith(_WRONG)
