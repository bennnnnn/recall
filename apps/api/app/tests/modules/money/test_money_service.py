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
