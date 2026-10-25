"""A money turn from message to reply: when it waits for the average, and what it adds."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import Settings
from app.modules.money import service
from app.modules.money.rates import MarketRate
from app.tests.modules.money.money_support import average

_SENTENCE = "what is my mortgage for 300k dollars house if mr rate is 1 percent"


def _lookup(monkeypatch, found: MarketRate | None, *, delay: float = 0.0) -> list[tuple]:
    calls: list[tuple] = []

    async def current_average(product, term, country, settings, redis, **_: Any):
        calls.append((product.key, term, country))
        await asyncio.sleep(delay)
        return found

    monkeypatch.setattr(service, "current_average", current_average)
    return calls


async def test_a_rate_given_does_not_wait_and_the_reply_gets_note_and_card(monkeypatch) -> None:
    calls = _lookup(monkeypatch, average(), delay=0.05)
    settings = Settings()
    turn = await service.prepare_money_turn(_SENTENCE, settings, None, user=None, location=None)
    assert turn is not None and turn.average is None and turn.worked is not None
    await asyncio.sleep(0)  # the lookup started with the turn, without being waited on
    assert calls == [("mortgage", 30, "the United States")]
    reply = await service.finish_money_reply(turn, "About $964.92 a month.", settings)
    assert reply.startswith("About $964.92 a month.\n\n**Note:** 1% is not a realistic")
    assert reply.rstrip().endswith("```") and "```calculator\n" in reply


async def test_no_rate_waits_for_the_average_and_uses_it(monkeypatch) -> None:
    _lookup(monkeypatch, average())
    turn = await service.prepare_money_turn(
        "monthly payment on a 250000 mortgage", Settings(), None, user=None, location=None
    )
    assert turn is not None and turn.worked is not None
    assert turn.worked.values["rate"] == 6.27 and "rate" in turn.worked.assumed


async def test_no_average_means_no_note_and_no_marker(monkeypatch) -> None:
    _lookup(monkeypatch, None)
    settings = Settings()
    turn = await service.prepare_money_turn(_SENTENCE, settings, None, user=None, location=None)
    assert turn is not None
    reply = await service.finish_money_reply(turn, "About $964.92 a month.", settings)
    assert "**Note:**" not in reply and '"marker"' not in reply and "```calculator" in reply


async def test_the_country_follows_the_currency(monkeypatch) -> None:
    calls = _lookup(monkeypatch, None)
    await service.prepare_money_turn(
        "mortgage of 2 million birr at 18% for 20 years", Settings(), None, user=None, location=None
    )
    await asyncio.sleep(0)
    assert calls == [("mortgage", 20, "Ethiopia")]


async def test_a_card_with_no_currency_named_uses_the_saved_place(monkeypatch) -> None:
    """ "I owe 5000 on my card" names no currency: the card is not left without one."""
    _lookup(monkeypatch, None)
    text = "I owe 5000 on my credit card at 22% APR and pay 200 a month"
    settings = Settings()
    for location, currency in ((None, "USD"), ("Addis Ababa, Ethiopia", "ETB")):
        turn = await service.prepare_money_turn(text, settings, None, user=None, location=location)
        assert turn is not None and turn.request.currency == currency
        assert f"Currency: {currency}." in turn.block
        reply = await service.finish_money_reply(turn, "About 34 months.", settings)
        assert f'"currency":"{currency}"' in reply


async def test_a_late_average_is_left_out(monkeypatch) -> None:
    _lookup(monkeypatch, average(), delay=10)
    monkeypatch.setattr(service, "_FINISH_WAIT_SECONDS", 0.01)
    settings = Settings()
    turn = await service.prepare_money_turn(_SENTENCE, settings, None, user=None, location=None)
    assert turn is not None
    reply = await service.finish_money_reply(turn, "About $964.92 a month.", settings)
    assert "**Note:**" not in reply
    assert turn.lookup is not None
    turn.lookup.cancel()


async def test_money_off_reads_nothing(monkeypatch) -> None:
    calls = _lookup(monkeypatch, None)
    settings = Settings(money_enabled=False)
    assert (
        await service.prepare_money_turn(_SENTENCE, settings, None, user=None, location=None)
        is None
    )
    assert calls == []


_USED = (
    "i'm thinking of buying a used car for 14000, i can put 3000 down. what would my monthly "
    "payment be over 5 years?"
)


def _lookup_kinds(monkeypatch, found: MarketRate | None) -> list[tuple]:
    calls: list[tuple] = []

    async def current_average(product, term, country, settings, redis, **kwargs: Any):
        calls.append((product.key, kwargs.get("variant", ""), term))
        return found

    monkeypatch.setattr(service, "current_average", current_average)
    return calls


async def test_a_used_car_looks_up_the_used_car_average(monkeypatch) -> None:
    """Live (2026-10-25): the used car was worked at the new-car average."""
    used = average(7.16, "60-month used car loan rate")
    calls = _lookup_kinds(monkeypatch, used)
    turn = await service.prepare_money_turn(_USED, Settings(), None, user=None, location=None)
    assert turn is not None and turn.worked is not None
    assert calls == [("car", "used", 60)]
    assert turn.block.startswith("Money, worked by the app: used car.")
    reply = await service.finish_money_reply(turn, "About $218.64 a month.", Settings())
    assert "today's average 60-month used car loan rate" in reply


async def test_a_what_if_after_a_money_reply_is_worked_by_the_server(monkeypatch) -> None:
    """Live (2026-10-25): the free model said $340.58 and $1,260.88 for this; the loan is
    11 000 at the same 7.16 % over 36 months: $340.45 a month, $1,256.32 interest."""
    calls = _lookup_kinds(monkeypatch, average(7.16, "60-month used car loan rate"))
    turn = await service.prepare_money_turn(
        "hmm what if i only do 3 years instead",
        Settings(),
        None,
        user=None,
        location=None,
        earlier=[_USED],
    )
    assert turn is not None and turn.worked is not None
    # The rate stays the one the last reply used: the 60-month average, looked up again.
    assert calls == [("car", "used", 60)]
    assert turn.worked.values["months"] == 36 and turn.worked.values["rate"] == 7.16
    assert round(turn.worked.outputs["payment"] or 0, 2) == 340.45
    assert round(turn.worked.outputs["interest"] or 0, 2) == 1256.32
    reply = await service.finish_money_reply(turn, "About $340.45 a month.", Settings())
    assert "```calculator\n" in reply and '"value":36' in reply


async def test_a_what_if_with_no_money_before_it_is_no_money_turn(monkeypatch) -> None:
    calls = _lookup_kinds(monkeypatch, None)
    workout = ["give me a 4 day workout plan with 4 sets of each exercise"]
    for line, earlier in (
        ("what if i only do 3 sets instead", workout),
        ("3 years", []),
        ("what if it was 3 years ago", [_USED]),
    ):
        assert (
            await service.prepare_money_turn(
                line, Settings(), None, user=None, location=None, earlier=earlier
            )
            is None
        )
    assert calls == []
