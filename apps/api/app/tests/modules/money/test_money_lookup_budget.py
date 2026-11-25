"""The money card's rate lookups beside the turn's own search, kept and shared once looked up,
and the request read once a turn, off the event loop (audit, 2026-11-25)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.config import Settings
from app.core.readings import begin_turn, kept_reading
from app.modules.chat.turn_prep.reading import read_turn_message
from app.modules.money import rates, service
from app.modules.money import reading as money_reading
from app.modules.money.catalog import product
from app.modules.money.rates import RateReading, current_average
from app.modules.web_search import SideSearchBudget, TurnTavilyBudget, side_search_budget
from app.tests.fakes import make_user
from app.tests.modules.money.money_support import HITS, TODAY

_COUNTRY = "the United States"


def test_a_free_turns_lookups_leave_it_its_one_search() -> None:
    """On Free the kind's lookup, its stand-in and the reply's search all ran on the turn's
    one search: one lookup never searched and the reply was refused its own."""
    kept: list[int] = []
    turn = TurnTavilyBudget(
        settings=Settings(), user=make_user(plan="free"), on_provider_call=lambda: kept.append(1)
    )
    side = side_search_budget(turn)
    assert isinstance(side, SideSearchBudget)
    assert side.begin_search() and side.begin_search()  # the kind's lookup and its stand-in
    side.note_provider_call()
    assert kept == [1]  # a lookup that reached a provider keeps the message, as any search
    assert turn.begin_search()  # the reply still searches
    assert not turn.begin_search()  # once
    side.record_search(failed=True)
    assert not turn.search_failed  # a failed lookup is no failed search of the reply's
    assert side_search_budget(None) is None


async def test_a_used_car_turn_starts_both_lookups_beside_the_turns_search(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any
) -> None:
    budgets: list[object] = []

    async def lookup(*_args: Any, budget: object = None, **_kwargs: Any) -> None:
        budgets.append(budget)

    monkeypatch.setattr(service, "current_average", lookup)
    turn = TurnTavilyBudget(settings=Settings(), user=make_user(plan="free"))
    await service.prepare_money_turn(
        "i'm thinking of buying a used car for 14000, i can put 3000 down. what would my monthly "
        "payment be over 60 months?",
        Settings(),
        fake_redis,
        user=None,
        location=None,
        search_budget=turn,
    )
    assert len(budgets) == 2
    assert all(isinstance(b, SideSearchBudget) and b.turn is turn for b in budgets)
    assert turn.begin_search()


def _search(calls: list[list[str]], *, delay: float = 0.0) -> Any:
    async def search(_settings: Settings, queries: list[str], **_: Any) -> tuple[list, list]:
        calls.append(queries)
        await asyncio.sleep(delay)
        return HITS, []

    return search


async def test_an_answer_with_no_rate_is_kept_briefly(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any
) -> None:
    calls: list[list[str]] = []

    async def nothing(**_: Any) -> RateReading:
        return RateReading(found=False)

    monkeypatch.setattr(rates, "run_cached_search", _search(calls))
    monkeypatch.setattr(rates.litellm_gateway, "complete_structured", nothing)
    for _ in range(3):
        assert (
            await current_average(
                product("mortgage"), 30, _COUNTRY, Settings(), fake_redis, today=TODAY
            )
            is None
        )
    assert len(calls) == 1
    key = "money:average:mortgage:30:the united states"
    assert await fake_redis.get(key) in ("missing", b"missing")
    assert 0 < await fake_redis.ttl(key) <= 15 * 60


async def test_a_failed_read_is_never_kept(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any
) -> None:
    calls: list[list[str]] = []

    async def broken(**_: Any) -> RateReading:
        raise TimeoutError

    monkeypatch.setattr(rates, "run_cached_search", _search(calls))
    monkeypatch.setattr(rates.litellm_gateway, "complete_structured", broken)
    for _ in range(2):
        await current_average(
            product("mortgage"), 30, _COUNTRY, Settings(), fake_redis, today=TODAY
        )
    assert len(calls) == 2


async def test_turns_asking_at_once_share_one_lookup(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any
) -> None:
    calls: list[list[str]] = []

    async def read(**_: Any) -> RateReading:
        return RateReading(
            found=True, rate_percent=6.27, as_of="2026-10-16", source_url=HITS[0].url
        )

    monkeypatch.setattr(rates, "run_cached_search", _search(calls, delay=0.05))
    monkeypatch.setattr(rates.litellm_gateway, "complete_structured", read)
    found = await asyncio.gather(
        *(
            current_average(product("mortgage"), 30, _COUNTRY, Settings(), fake_redis, today=TODAY)
            for _ in range(4)
        )
    )
    assert len(calls) == 1
    assert all(rate is not None and rate.value == 6.27 for rate in found)
    assert not rates._IN_FLIGHT


async def test_a_turns_money_request_is_read_with_its_message_in_the_pool(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any
) -> None:
    """The turn's pool read reads the request; the money turn reads nothing again."""
    text = "what's the monthly payment on a 20000 car loan at 6% for 5 years"
    settings = Settings()
    begin_turn()
    await read_turn_message(text, [], settings)
    assert kept_reading(money_reading.request_of, text, ()) is not None

    def never(*_args: Any) -> None:
        raise AssertionError("read again")

    monkeypatch.setattr(money_reading, "follow_up_request", never)
    monkeypatch.setattr(money_reading, "read_money_request", never)
    turn = await service.prepare_money_turn(text, settings, fake_redis, user=None, location=None)
    assert turn is not None and turn.request.product.key == "car"
