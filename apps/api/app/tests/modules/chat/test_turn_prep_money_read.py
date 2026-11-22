"""The owner's chat of 2026-11-22: a car loan, then a mortgage, told over many short lines.

Every turn had ``money: None``: no word rule read "What would be my exact monthly payment ?",
"The interest is 6", "Down payment is 20 percent" or "72 months", so the reply's model did
the sums, and its "correction" to $4,550.63 was wrong. A turn the read calls money now has
the chat's request written down by a model (faked here), each value held to the chat, and
the server's payment with a calculator card.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.readings import begin_turn, keep_for_turn
from app.modules.chat.figure_turn import LIVE_READ
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep import money as money_prep
from app.modules.chat.turn_prep.reading import read_turn_message
from app.modules.money import service
from app.modules.money.block import MONEY_AMOUNT_MISSING
from app.modules.money.model_read import MoneyReading, StatedValue
from app.modules.turn_reading.plan import single_plan
from app.tests.modules.money.money_support import average

_CHAT: list[tuple[str, str]] = [
    ("user", "Is 3 per hour a good salary ?"),
    ("assistant", "$3 an hour is very low in most places."),
    ("user", "Is it a good idea tp buy a car for 40k?"),
    ("assistant", "It depends on your income and savings."),
    ("user", "My monthly is 20k"),
    ("assistant", "On $20k a month a $40k car is affordable."),
    ("user", "What would be my exact monthly payment ?"),
    ("assistant", "At 6% over 60 months, M ≈ $773."),
    ("user", "The interest is 6"),
    ("assistant", "At 6% for 60 months, about $773 a month."),
    ("user", "Down payment is 20 percent"),
    ("assistant", "With $8,000 down you borrow $32,000: about $619 a month."),
    ("user", "72 months"),
    ("assistant", "About $542 a month."),
    ("user", "Calculate the mortgage i can aford"),
    ("assistant", "Tell me your income and debts."),
    ("user", "0 debt, 200k a year"),
    ("assistant", "You could afford roughly a $750,000 home."),
    ("user", "Why are u not using the calculator"),
    ("assistant", "I did the arithmetic by hand."),
    ("user", "U come up with the loan amount. Rate is 6, term is 36 months"),
    ("assistant", "Let's take a loan of $150,000: at 6% over 36 months that is $4,563 a month."),
    ("user", "But u didn't use the built in calculator"),
    ("assistant", "Corrected: $4,550.63 a month."),
    ("user", "What is the monthly payment for $750k?"),
    ("assistant", "At 6% over 30 years, about $4,497 a month."),
    ("user", "Can I afford a $1 million home?"),
]

_PRICE = ("price", 40000, "a car for 40k")
_RATE = ("rate", 6, "The interest is 6")
_DOWN = ("down_percent", 20, "20 percent")


def _values(*items: tuple[str, float, str], by: str = "user") -> list[StatedValue]:
    return [
        StatedValue.model_validate({"name": name, "value": value, "quote": quote, "from": by})
        for name, value, quote in items
    ]


# Each turn: its line, the model's reading of the chat then, the server's payment.
_TURNS = [
    ("What would be my exact monthly payment ?", "car", _values(_PRICE), 773.31),
    ("The interest is 6", "car", _values(_PRICE, _RATE), 773.31),
    ("Down payment is 20 percent", "car", _values(_PRICE, _RATE, _DOWN), 618.65),
    ("72 months", "car", _values(_PRICE, _RATE, _DOWN, ("months", 72, "72 months")), 530.33),
    (
        "But u didn't use the built in calculator",
        "mortgage",
        _values(("amount", 150000, "$150,000"), by="assistant")
        + _values(("rate", 6, "Rate is 6"), ("months", 36, "36 months")),
        4563.29,
    ),
    (
        "What is the monthly payment for $750k?",
        "mortgage",
        _values(("amount", 750000, "$750k"), ("rate", 6, "Rate is 6")),
        4496.63,
    ),
]


async def _decided(subject: str) -> TurnDecision:
    return TurnDecision(live=False, subject=subject)  # type: ignore[arg-type]


def _setup(monkeypatch: pytest.MonkeyPatch, reading: MoneyReading | None, subject: str) -> list:
    seen: list = []

    async def read(settings: Settings, conversation: Any, text: str, **_: Any) -> Any:
        seen.append((list(conversation), text))
        return reading

    async def current_average(*_args: Any, **_kwargs: Any) -> Any:
        return average(6.0, "60-month new car loan rate")

    monkeypatch.setattr(service, "read_money_chat", read)
    monkeypatch.setattr(service, "current_average", current_average)
    begin_turn()
    keep_for_turn(LIVE_READ, asyncio.create_task(_decided(subject)))
    return seen


def _request(line: str) -> Any:
    index = next(i for i, (role, text) in enumerate(_CHAT) if role == "user" and text == line)
    rows = [SimpleNamespace(role=role, content=text) for role, text in _CHAT[: index + 1]]
    return SimpleNamespace(content=line, has_image_attachment=False, recent_messages=rows)


async def _run(
    line: str, redis: Redis, settings: Settings | None = None, request: Any = None
) -> Any:
    """The money prep as a real turn runs it: the message and the earlier lines read in the
    pool first."""
    settings = settings or Settings()
    request = request or _request(line)
    await read_turn_message(request.content, request.recent_messages, settings)
    return await money_prep.money_turn(request, _identity(), settings, redis, single_plan(line))


def _identity() -> Any:
    return SimpleNamespace(
        user=None,
        geo=SimpleNamespace(user_location=None),
        mode=SimpleNamespace(lightweight=False),
    )


@pytest.mark.parametrize(("line", "product", "values", "payment"), _TURNS)
async def test_each_turn_gets_the_servers_payment_and_a_card(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: Redis,
    thread_sympy_executor: None,
    line: str,
    product: str,
    values: list[StatedValue],
    payment: float,
) -> None:
    reading = MoneyReading(calculate=True, product=product, values=values)  # type: ignore[arg-type]
    seen = _setup(monkeypatch, reading, "money")
    turn = await _run(line, fake_redis)
    assert turn is not None and turn.worked is not None
    assert round(turn.worked.outputs["payment"] or 0, 2) == payment
    # The read saw the chat before the line, never the line twice.
    assert seen[0][1] == line and seen[0][0][-1][1] != line
    reply = await service.finish_money_reply(turn, "Here it is.", Settings())
    assert "```calculator\n" in reply


async def test_a_reply_proposed_amount_is_said_as_the_replys(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Redis, thread_sympy_executor: None
) -> None:
    line, product, values, _ = _TURNS[4]
    reading = MoneyReading(calculate=True, product=product, values=values)  # type: ignore[arg-type]
    _setup(monkeypatch, reading, "money")
    turn = await _run(line, fake_redis)
    assert turn is not None and "proposed in an earlier reply" in turn.block


async def test_advice_the_read_calls_everyday_is_never_read_for_money(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Redis, thread_sympy_executor: None
) -> None:
    line = "Is 3 per hour a good salary ?"
    seen = _setup(monkeypatch, MoneyReading(calculate=True, product="loan"), "everyday")
    request = SimpleNamespace(content=line, has_image_attachment=False, recent_messages=[])
    turn = await _run(line, fake_redis, request=request)
    assert turn is None and seen == []


async def test_a_money_read_that_asks_nothing_leaves_the_turn(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Redis, thread_sympy_executor: None
) -> None:
    line = "Is it a good idea tp buy a car for 40k?"
    reading = MoneyReading(calculate=False, product="car", values=_values(_PRICE))
    _setup(monkeypatch, reading, "money")
    turn = await _run(line, fake_redis)
    assert turn is None


async def test_no_amount_yet_asks_for_it_and_works_nothing(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Redis, thread_sympy_executor: None
) -> None:
    line = "U come up with the loan amount. Rate is 6, term is 36 months"
    values = _values(("rate", 6, "Rate is 6"), ("months", 36, "36 months"))
    _setup(monkeypatch, MoneyReading(calculate=True, product="loan", values=values), "money")
    turn = await _run(line, fake_redis)
    assert turn is not None and turn.worked is None
    assert MONEY_AMOUNT_MISSING.format(what="amount") in turn.block
    assert turn.lookup is None  # nothing to work: no search is spent on today's average
    assert await service.finish_money_reply(turn, "How much?", Settings()) == "How much?"


async def test_the_read_off_reads_no_money(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Redis, thread_sympy_executor: None
) -> None:
    line, product, values, _ = _TURNS[0]
    reading = MoneyReading(calculate=True, product=product, values=values)  # type: ignore[arg-type]
    seen = _setup(monkeypatch, reading, "money")
    off = Settings(money_read_enabled=False)
    turn = await _run(line, fake_redis, off)
    assert turn is None and seen == []


_INCOME = _values(("income", 200000, "200k a year"), ("debts", 0, "0 debt"))


@pytest.mark.parametrize(
    ("line", "extra"),
    [
        ("0 debt, 200k a year", []),
        ("Can I afford a $1 million home?", _values(("price", 1e6, "$1 million home"))),
    ],
)
async def test_what_an_income_affords_is_the_servers(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: Redis,
    thread_sympy_executor: None,
    line: str,
    extra: list[StatedValue],
) -> None:
    """Turns 9 and 14: the most the income borrows by the 28/36 rule, at today's average
    (faked 6%) over the default 30 years, with its card."""
    reading = MoneyReading(calculate=True, product="afford", values=_INCOME + extra)
    _setup(monkeypatch, reading, "money")
    turn = await _run(line, fake_redis)
    assert turn is not None and turn.worked is not None
    assert round(turn.worked.outputs["most_loan"] or 0, 2) == 778360.87
    assert ("costs 1,000,000" in turn.block) == bool(extra)
    reply = await service.finish_money_reply(turn, "Here it is.", Settings())
    assert '"product":"afford"' in reply


async def test_an_amount_from_an_older_reply_is_no_proposal(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Redis, thread_sympy_executor: None
) -> None:
    """Turn 11, read live: the car's "$32,000" from three replies before, taken as the
    mortgage's amount. Only the last reply proposes one."""
    line = "U come up with the loan amount. Rate is 6, term is 36 months"
    values = _values(("amount", 32000, "you borrow $32,000"), by="assistant") + _values(
        ("rate", 6, "Rate is 6"), ("months", 36, "36 months")
    )
    _setup(monkeypatch, MoneyReading(calculate=True, product="loan", values=values), "money")
    assert await _run(line, fake_redis) is None
