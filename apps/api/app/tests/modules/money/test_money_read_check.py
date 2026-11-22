"""A model's reading of the chat's money request is held to the chat's words."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.money.block import MONEY_AMOUNT_MISSING, money_block
from app.modules.money.model_read import MoneyReading, StatedValue, chat_lines, read_money_chat
from app.modules.money.read import sized
from app.modules.money.read_check import Chat, checked_request
from app.modules.money.solve import missing

_CHAT = Chat(
    user_lines=[
        "Is it a good idea tp buy a car for 40k?",
        "My monthly is 20k",
        "The interest is 6",
        "Down payment is 20 percent",
        "72 months",
    ],
    replies=["If you borrow $150,000 at 6% over 36 months the payment is about $4,563."],
)


def _reading(product: str = "car", *values: tuple[str, float, str], **kw: Any) -> MoneyReading:
    return MoneyReading(
        calculate=kw.get("calculate", True),
        product=product,  # type: ignore[arg-type]
        plain=kw.get("plain", True),
        used=kw.get("used", False),
        values=[
            StatedValue.model_validate(
                {
                    "name": name,
                    "value": value,
                    "quote": quote,
                    "from": kw.get("by", {}).get(name, "user"),
                }
            )
            for name, value, quote in values
        ],
    )


def test_values_over_several_lines_make_one_request() -> None:
    request = checked_request(
        _reading(
            "car",
            ("price", 40000, "a car for 40k"),
            ("rate", 6, "The interest is 6"),
            ("down_percent", 20, "20 percent"),
            ("months", 72, "72 months"),
        ),
        _CHAT,
    )
    assert request is not None and request.product.key == "car"
    assert request.values == {"amount": 32000, "rate": 6, "months": 72}
    assert (request.price, request.down) == (40000, 8000)


@pytest.mark.parametrize(
    ("value", "quote"),
    [
        (50000, "a car for 40k"),  # the quote holds another number
        (40000, "a truck for 40k"),  # the quote is in no line of the chat
        (40000, ""),
    ],
)
def test_a_value_not_held_by_its_quote_reads_no_request(value: float, quote: str) -> None:
    assert checked_request(_reading("car", ("price", value, quote)), _CHAT) is None


def test_advice_a_comparison_or_no_product_is_no_request() -> None:
    price = ("price", 40000, "a car for 40k")
    assert checked_request(_reading("car", price, calculate=False), _CHAT) is None
    assert checked_request(_reading("car", price, plain=False), _CHAT) is None
    assert checked_request(_reading("none", price), _CHAT) is None
    twice = _reading("car", ("rate", 6, "The interest is 6"), ("rate", 20, "20 percent"), price)
    assert checked_request(twice, _CHAT) is None


def test_a_rate_the_product_is_never_charged_reads_none() -> None:
    chat = Chat(user_lines=["a car for 40k at 60"], replies=[])
    reading = _reading("car", ("price", 40000, "40k"), ("rate", 60, "at 60"))
    assert checked_request(reading, chat) is None


def test_only_an_amount_is_taken_from_a_reply() -> None:
    by = {"amount": "assistant", "rate": "assistant"}
    proposed = _reading("loan", ("amount", 150000, "$150,000"), by={"amount": "assistant"})
    request = checked_request(proposed, _CHAT)
    assert request is not None and request.values["amount"] == 150000
    assert request.proposed == ("amount",)
    # A rate only the reply assumed is dropped: today's average or the default stands in.
    rate = _reading("loan", ("amount", 150000, "$150,000"), ("rate", 6, "at 6%"), by=by)
    request = checked_request(rate, _CHAT)
    assert request is not None and "rate" not in request.values


def test_a_term_off_the_mortgage_slider_is_a_plain_loan() -> None:
    chat = Chat(user_lines=["Rate is 6, term is 36 months", "$150k"], replies=[])
    reading = _reading(
        "mortgage",
        ("amount", 150000, "$150k"),
        ("rate", 6, "Rate is 6"),
        ("months", 36, "36 months"),
    )
    request = checked_request(reading, chat)
    assert request is not None and request.product.key == "loan"
    assert request.values == {"amount": 150000, "rate": 6, "years": 3}


def test_a_request_with_nothing_to_size_it_asks_for_the_amount() -> None:
    chat = Chat(user_lines=["what would my payment be at 6 percent"], replies=[])
    request = checked_request(_reading("car", ("rate", 6, "6 percent")), chat)
    assert request is not None and not sized(request) and request.values == {"rate": 6}


def test_the_used_kind_needs_the_users_word() -> None:
    price = ("price", 14000, "14000")
    said = Chat(user_lines=["a used car for 14000"], replies=[])
    unsaid = Chat(user_lines=["a car for 14000"], replies=[])
    assert checked_request(_reading("car", price, used=True), said).variant == "used"  # type: ignore[union-attr]
    assert checked_request(_reading("car", price, used=True), unsaid).variant == ""  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("quote", "value"),
    [("$750k", 750000), ("a $1 million home", 1e6), ("a million", 1e6), ("five years", 5)],
)
def test_a_quote_holds_its_number_however_it_is_written(quote: str, value: float) -> None:
    chat = Chat(user_lines=[f"mortgage of 300000 on {quote}"], replies=[])
    name = "years" if "year" in quote else "amount"
    reading = _reading("mortgage", (name, value, quote), ("amount", 300000, "300000"))
    if name == "amount":
        reading = _reading("mortgage", (name, value, quote))
    request = checked_request(reading, chat)
    assert request is not None and value in request.values.values()


def test_the_model_writes_from_and_unknown_names_drop() -> None:
    reading = MoneyReading.model_validate(
        {
            "calculate": True,
            "product": "Car",
            "values": [
                {"name": "price", "value": 40000, "quote": "40k", "from": "assistant"},
                {"name": "salary", "value": 20000, "quote": "20k"},
            ],
        }
    )
    assert reading.product == "car" and [item.name for item in reading.values] == ["price"]
    assert reading.values[0].said_by == "assistant"


def test_the_read_sees_the_chat_with_the_last_line_marked() -> None:
    text = chat_lines([("user", "a car for 40k"), ("assistant", "Nice.")], "72 months")
    assert text.splitlines() == [
        "User: a car for 40k",
        "Assistant: Nice.",
        "User (last): 72 months",
    ]


_AFFORD = Chat(
    user_lines=["My monthly is 20k", "0 debt, 200k a year", "Can I afford a $1 million home?"],
    replies=[],
)


def test_what_an_income_affords_reads_its_income_debts_and_price() -> None:
    reading = _reading(
        "afford",
        ("income", 200000, "200k a year"),
        ("debts", 0, "0 debt"),
        ("price", 1e6, "$1 million home"),
    )
    request = checked_request(reading, _AFFORD)
    assert request is not None and request.product.key == "afford"
    assert request.values == {"income": 200000, "debts": 0} and request.price == 1e6


def test_an_income_is_read_by_its_own_period() -> None:
    monthly = _reading("afford", ("monthly_income", 20000, "My monthly is 20k"))
    request = checked_request(monthly, _AFFORD)
    assert request is not None and request.values["income"] == 240000
    # A month's income read as a year's is a misreading: nothing is worked.
    assert (
        checked_request(_reading("afford", ("income", 20000, "My monthly is 20k")), _AFFORD) is None
    )


def test_an_income_never_sizes_a_loan() -> None:
    reading = _reading("car", ("income", 200000, "200k a year"), ("rate", 6, "6"))
    request = checked_request(reading, Chat(user_lines=["200k a year at 6"], replies=[]))
    assert request is not None and not sized(request)


def test_a_reading_with_no_value_is_left_to_the_reply() -> None:
    assert checked_request(_reading("afford"), _AFFORD) is None


@pytest.mark.parametrize("gate", [AsyncMock(return_value=True), AsyncMock(side_effect=OSError)])
async def test_no_money_read_past_the_spend_cap_or_in_an_outage(gate: AsyncMock) -> None:
    with (
        patch("app.core.redis.get_redis_client", MagicMock()),
        patch("app.services.quota.global_spend_exceeded", gate),
        patch("app.gateways.structured_completion.complete_structured", AsyncMock()) as call,
    ):
        assert await read_money_chat(Settings(), [], "72 months") is None
    call.assert_not_awaited()


def test_a_value_that_is_no_number_is_no_reading() -> None:
    with pytest.raises(ValidationError):
        StatedValue.model_validate({"name": "price", "value": float("inf"), "quote": "40k"})


def test_nothing_down_borrows_the_whole_price() -> None:
    chat = Chat(user_lines=["a car for 40k, 0% down"], replies=[])
    reading = _reading("car", ("price", 40000, "40k"), ("down_percent", 0, "0% down"))
    request = checked_request(reading, chat)
    assert request is not None and request.values["amount"] == 40000


def test_what_is_missing_is_what_the_block_asks_for() -> None:
    card = Chat(user_lines=["I owe $6,000 on my card", "APR is 24%"], replies=[])
    reading = _reading("card", ("balance", 6000, "$6,000"), ("apr", 24, "24%"))
    request = checked_request(reading, card)
    assert request is not None and missing(request) == ("payment",)
    block = money_block(request, None, None)
    assert MONEY_AMOUNT_MISSING.format(what="monthly payment") in block
    # What an income affords, with a home's price and no income: the income is asked for,
    # and a price of 0 ("0 debt") is no price.
    home = Chat(user_lines=["Can I afford a $1 million home?"], replies=[])
    afford = checked_request(_reading("afford", ("price", 1e6, "$1 million home")), home)
    assert afford is not None and afford.price == 1e6
    assert MONEY_AMOUNT_MISSING.format(what="yearly gross income") in money_block(
        afford, None, None
    )
    zero = Chat(user_lines=["0 debt, 200k a year"], replies=[])
    reading = _reading("afford", ("income", 200000, "200k a year"), ("price", 0, "0 debt"))
    assert checked_request(reading, zero).price is None  # type: ignore[union-attr]
