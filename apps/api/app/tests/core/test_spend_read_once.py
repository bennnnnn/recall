"""Today's spend is read once per chat turn, and the skip-on-cap-or-outage rule is written
once (audit, 2026-11-25): a turn's admission, live read, figure, chart and formal reads,
tool loop, follow-ups and post-turn jobs each sent the same GET."""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import readings
from app.core.config import Settings
from app.core.spend_counter import global_spend_exceeded, spend_key, spend_pause_reason
from app.exceptions import RedisUnavailableError

_CAPPED = Settings(daily_global_spend_usd=1.0)


class _CountingRedis:
    def __init__(self, spent: int, *, down: bool = False) -> None:
        self.spent, self.down, self.gets = spent, down, 0

    async def get(self, key: str) -> Any:
        assert key == spend_key()
        self.gets += 1
        if self.down:
            raise RedisConnectionError("down")
        return str(self.spent)


async def _in_a_turn(redis: _CountingRedis) -> list[bool]:
    readings.begin_turn()
    first = await global_spend_exceeded(redis, _CAPPED)  # type: ignore[arg-type]
    # Tasks the turn starts share its read, as the figure and chart reads do.
    rest = await asyncio.gather(
        *(asyncio.create_task(global_spend_exceeded(redis, _CAPPED)) for _ in range(4))  # type: ignore[arg-type]
    )
    return [first, *rest]


@pytest.mark.asyncio
async def test_a_turn_reads_the_spend_once() -> None:
    redis = _CountingRedis(2_000_000)
    answers = await contextvars.copy_context().run(asyncio.ensure_future, _in_a_turn(redis))
    assert answers == [True] * 5
    assert redis.gets == 1


@pytest.mark.asyncio
async def test_outside_a_turn_each_check_reads_it() -> None:
    redis = _CountingRedis(0)
    for _ in range(3):
        assert (
            await contextvars.Context().run(
                asyncio.ensure_future,
                global_spend_exceeded(redis, _CAPPED),  # type: ignore[arg-type]
            )
            is False
        )
    assert redis.gets == 3


@pytest.mark.asyncio
async def test_a_turn_whose_read_failed_is_unavailable_at_every_check() -> None:
    redis = _CountingRedis(0, down=True)

    async def turn() -> int:
        readings.begin_turn()
        failures = 0
        for _ in range(3):
            try:
                await global_spend_exceeded(redis, _CAPPED)  # type: ignore[arg-type]
            except RedisUnavailableError:
                failures += 1
        return failures

    assert await contextvars.copy_context().run(asyncio.ensure_future, turn()) == 3
    assert redis.gets == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("check", "reason"),
    [
        (AsyncMock(return_value=False), None),
        (AsyncMock(return_value=True), "global spend cap"),
        (AsyncMock(side_effect=RedisUnavailableError()), "global spend unreadable (Redis down)"),
    ],
)
async def test_work_nobody_waits_on_skips_at_the_cap_or_in_an_outage(
    check: AsyncMock, reason: str | None
) -> None:
    assert await spend_pause_reason(check, AsyncMock(), _CAPPED) == reason


@pytest.mark.asyncio
async def test_a_cap_crossed_mid_turn_stops_the_turn_s_later_extras(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The turn's checks share one read only for ``TURN_SPEND_SHARED_SECONDS``: its tool loop
    and follow-ups, later, see a cap this turn or another crossed meanwhile, and a Redis
    error then counts as over the cap (docs/PRODUCTION.md; review of #2592)."""
    from app.core import spend_counter

    clock = [100.0]
    monkeypatch.setattr(spend_counter, "_monotonic", lambda: clock[0])
    redis = _CountingRedis(0)

    async def turn() -> list[str | None]:
        readings.begin_turn()
        admitted = await spend_pause_reason(global_spend_exceeded, redis, _CAPPED)  # type: ignore[arg-type]
        redis.spent = 2_000_000  # the cap is crossed while the reply streams
        alongside = await spend_pause_reason(global_spend_exceeded, redis, _CAPPED)  # type: ignore[arg-type]
        clock[0] += 5.0  # the follow-ups, after the reply
        later = await spend_pause_reason(global_spend_exceeded, redis, _CAPPED)  # type: ignore[arg-type]
        redis.down = True
        clock[0] += 5.0
        outage = await spend_pause_reason(global_spend_exceeded, redis, _CAPPED)  # type: ignore[arg-type]
        return [admitted, alongside, later, outage]

    answers = await contextvars.copy_context().run(asyncio.ensure_future, turn())
    assert answers == [
        None,
        None,  # read together with the admission: the same read
        "global spend cap",
        "global spend unreadable (Redis down)",
    ]
    assert redis.gets == 3
