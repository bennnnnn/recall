"""A money reply agrees with the card the server built, or the server writes it."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import Settings
from app.modules.money.agreement import agrees_with_card, keep_to_the_card, worked_reply
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


def _house():
    request = purchase_request("60k at 6 percent", ("House buying for 400k",))
    assert request is not None
    request = replace(request, currency="USD")
    worked = work(request, None)
    assert worked is not None
    return request, worked


def test_the_live_reply_is_written_by_the_server() -> None:
    request, worked = _house()

    fixed = keep_to_the_card(_WRONG, request, worked)

    assert fixed == (
        "For a $340,000 mortgage at 6% over 30 years, the monthly payment is **$2,038.47**. "
        "Total interest is $393,849.84, and the total paid is $733,849.84. No term was "
        "given, so it uses 30 years."
    )


@pytest.mark.parametrize(
    "reply",
    [
        "Your monthly payment on a $340,000 mortgage at 6% over 30 years is **$2,038.47**.",
        # The server's figures rounded to the unit or in thousands, or in LaTeX.
        "That comes to about $2,038 a month, with ~$393,850 in interest.",
        "Putting $60k down on a $400k house leaves $340k to borrow.",
        "$M \\approx \\$2{,}038.47$",
        # Percents, terms and plain counts are no sums of money.
        "At 6% over 30 years (360 months) that is $2,038.47.",
        # No sums at all: the card shows them.
        "Here are your numbers. The card below lets you try other terms.",
    ],
)
def test_a_reply_with_only_the_cards_sums_keeps_its_words(reply: str) -> None:
    request, worked = _house()

    assert agrees_with_card(reply, request, worked)
    assert keep_to_the_card(reply, request, worked) == reply


@pytest.mark.parametrize(
    "reply",
    [
        _WRONG,
        # A total with the price in it, a payment worked wrong by 50 cents, another
        # principal, or a sum about something else: none is the card's.
        "Total cost of the home: ~$793,850 (price + interest).",
        "The payment is $2,037.97 a month.",
        "With $80,000 down, the payment is $1,918.56 a month.",
        "Your rent is $1,950.00 and the mortgage is $2,038.47.",
    ],
)
def test_a_reply_with_another_sum_is_the_servers(reply: str) -> None:
    request, worked = _house()

    assert not agrees_with_card(reply, request, worked)
    assert keep_to_the_card(reply, request, worked).startswith("For a $340,000 mortgage")


def test_the_users_own_numbers_may_be_repeated() -> None:
    request, worked = _house()
    reply = "Your rent is $1,950.00 and the mortgage is $2,038.47."

    assert agrees_with_card(reply, request, worked, "I pay 1950 rent, is buying better?")


def test_a_sum_in_code_is_not_read() -> None:
    request, worked = _house()

    assert agrees_with_card("```python\npayment = 359.82\n```\n$2,038.47", request, worked)


def test_the_down_payment_follow_up_reply_agrees() -> None:
    request = read_money_request("car loan 17000 at 6% for 60 months")
    assert request is not None
    worked = work(request, None)
    assert worked is not None

    assert agrees_with_card("You'd borrow $17,000 at **$328.66** a month.", request, worked)
    assert not agrees_with_card("You'd borrow $17,000 at **$328.16** a month.", request, worked)


def test_card_and_savings_replies() -> None:
    card = read_money_request("credit card balance 5000 at 22% apr paying 200 a month")
    savings = read_money_request("save 200 a month from 1000 at 4% for 10 years")
    assert card is not None and savings is not None
    card_worked, savings_worked = work(card, None), work(savings, None)
    assert card_worked is not None and savings_worked is not None

    assert worked_reply(card, card_worked).startswith("Paying 200 a month on a 5,000 balance")
    assert "months**" in worked_reply(card, card_worked)
    assert "grows to **" in worked_reply(savings, savings_worked)
    never = read_money_request("credit card balance 5000 at 22% apr paying 50 a month")
    assert never is not None
    never_worked = work(never, None)
    assert never_worked is not None
    assert "never clears it" in worked_reply(never, never_worked)


def _turn(*, multi: bool = False) -> MoneyTurn:
    request, worked = _house()
    return MoneyTurn(request, worked, money_block(request, worked, None), None, None, multi=multi)


async def test_finish_replaces_only_an_english_single_request_reply() -> None:
    settings = Settings()

    english = await finish_money_reply(_turn(), _WRONG, settings)
    other = await finish_money_reply(_turn(), _WRONG, settings, english=False)
    multi = await finish_money_reply(_turn(multi=True), _WRONG, settings)

    assert english.startswith("For a $340,000 mortgage")
    assert "**Read as:**" in english and "```calculator" in english
    assert other.startswith(_WRONG) and multi.startswith(_WRONG)
