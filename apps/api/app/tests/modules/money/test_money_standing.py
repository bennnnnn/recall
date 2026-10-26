"""A turn about the chat's earlier loan: its figures for the model, and the reply's sums checked."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.money.block import MONEY_HEADER, MONEY_STANDING_HEADER
from app.modules.money.follow_up import standing_request
from app.modules.money.note import reading_note
from app.modules.money.purchase import purchase_request
from app.modules.money.service import finish_money_reply, prepare_standing_turn
from app.modules.money.solve import work
from app.modules.money.standing import about_the_loan, correct_figures

# The live chat (2026-10-25): a 400k house, 60k down at 6%, then "How", "Yes", "Yes".
_HOUSE = [("House buying for 400k",), ("60k at 6 percent",), ("How",), ("Yes",)]
_OFFER = "If you'd like, I can show how a 15-year term changes the monthly payment."
_LIVE_REPLY = (
    "Here's the 15-year comparison for the same $340,000 loan at 6%.\n\n"
    "$M \\approx \\$2{,}921.00$\n\n"
    "$2{,}921.00 \\times 180 - 340{,}000 = \\$185{,}780.00$\n\n"
    "Compared with the 30-year loan, the payment rises by about $883."
)


def _house():
    request = standing_request(_HOUSE)
    assert request is not None
    worked = work(request, None)
    assert worked is not None
    return request, worked


def test_the_house_still_stands_after_lines_about_something_else() -> None:
    request, worked = _house()

    assert request.product.key == "mortgage"
    assert worked.values["amount"] == 340_000
    assert round(worked.outputs["payment"] or 0, 2) == 2038.47


def test_the_live_15_year_figures_are_put_right() -> None:
    request, worked = _house()

    fixed = correct_figures(_LIVE_REPLY, request, worked)

    assert "\\$2{,}869.11$" in fixed
    assert "\\$176{,}440.38$" in fixed
    assert "2{,}869.11 \\times 180" in fixed
    # The loan, the price and rough figures stay as written.
    assert "340{,}000" in fixed and "about $883" in fixed


@pytest.mark.parametrize(
    "reply",
    [
        # A right figure at a term the grid holds, rounded either way.
        "Over 25 years the payment is $2,190.62.",
        "Over 15 years the payment is $2,869.10.",
        # Another rate: a loan the app did not work.
        "At 5.5% over 15 years the payment is $2,778.07.",
        # Figures nowhere near the loan's, and the price.
        "Taxes run about $4,800.00 a year on a $400,000.00 home.",
        # Inside code.
        "```\npayment = 2921.00\n```",
        # No cents: not judged.
        "About $2,921 a month over 15 years.",
        # Another loan at the same rate and term: its figures are its own.
        "A $350,000 loan over 30 years would be $2,098.43 a month.",
        "If you borrow 330k instead, the payment is $1,978.52.",
        "On a $420,000 house with the same 60k down, it is $2,158.38.",
    ],
)
def test_other_sums_stay_as_written(reply: str) -> None:
    request, worked = _house()

    assert correct_figures(reply, request, worked) == reply


def test_a_sum_near_two_figures_stays() -> None:
    request, worked = _house()
    # 15 years: 2,869.11; 20 years: 2,435.87. Halfway is near neither within the margin,
    # and a sum between two close figures is never guessed.
    reply = "Over 15 or 20 years the payment is $2,650.00."

    assert correct_figures(reply, request, worked) == reply


@pytest.mark.parametrize(
    ("text", "last_reply", "about"),
    [
        ("Yes", _OFFER, True),
        ("How", _OFFER, True),
        ("show me the math", _OFFER, True),
        ("what about 20 years?", "", True),
        ("can I afford that?", "", True),
        ("thanks", _OFFER, False),
        ("what's the weather like today?", _OFFER, False),
        ("how do I bake bread?", _OFFER, False),
        ("Yes", "Mix flour, water and yeast. Want a full recipe?", False),
        ("tell me a joke", _OFFER, False),
    ],
)
def test_about_the_loan(text: str, last_reply: str, about: bool) -> None:
    assert about_the_loan(text, last_reply) is about


async def test_a_yes_about_the_loan_gets_its_figures_and_no_card() -> None:
    turn = await prepare_standing_turn(
        "Yes", Settings(), None, user=None, location=None, earlier=_HOUSE, last_reply=_OFFER
    )

    assert turn is not None and turn.standing
    assert turn.block.startswith(MONEY_STANDING_HEADER)
    assert MONEY_HEADER + ":" not in turn.block
    assert "With term in years 15: monthly payment 2,869.11" in turn.block
    assert "monthly payment 2,038.47" in turn.block
    finished = await finish_money_reply(turn, _LIVE_REPLY, Settings())
    assert "```calculator" not in finished and "**Note:**" not in finished
    assert "2{,}869.11" in finished


@pytest.mark.parametrize(
    "earlier",
    [
        [],
        [("How do I start running?",), ("Yes",)],
        [("what are mortgage rates now?",)],
    ],
)
async def test_no_loan_in_the_chat_no_block(earlier: list[tuple[str, ...]]) -> None:
    turn = await prepare_standing_turn(
        "Yes", Settings(), None, user=None, location=None, earlier=earlier, last_reply=_OFFER
    )

    assert turn is None


async def test_money_off_no_block() -> None:
    settings = Settings(money_enabled=False)

    turn = await prepare_standing_turn(
        "Yes", settings, None, user=None, location=None, earlier=_HOUSE, last_reply=_OFFER
    )

    assert turn is None


def test_a_reply_that_says_the_reading_gets_only_the_fix_line() -> None:
    request = purchase_request("60k at 6 percent", ("House buying for 400k",))
    assert request is not None
    said = "I treated your $60,000 as the down payment on the $400,000 price."

    assert reading_note(request, said) == "If 60,000 is the loan, not the down payment, say so."
    # No reading in the reply, or another price in the sentence: the whole note.
    for reply in ("Your payment is $2,038.47.", "Put $60,000 down on any $500,000 home."):
        assert (reading_note(request, reply) or "").startswith("**Read as:**")
