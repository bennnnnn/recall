import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.background import periodic
from app.core.config import Settings


@pytest.mark.asyncio
async def test_run_locked_cycle_skips_lock_when_disabled():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    fn = AsyncMock()
    settings = Settings()

    with patch("app.background.periodic.get_redis_client", return_value=redis):
        await periodic.run_locked_cycle(
            name="test",
            lock_key="k",
            lock_ttl_seconds=60,
            enabled=False,
            fn=fn,
            settings=settings,
        )

    redis.set.assert_not_awaited()
    fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_periodic_does_not_spawn_when_disabled():
    settings = Settings()
    cycle = AsyncMock()
    await periodic.start_periodic(
        name="disabled-sched",
        interval_seconds=60,
        enabled=False,
        cycle=cycle,
        settings=settings,
    )
    assert "disabled-sched" not in periodic._tasks
    cycle.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_periodic_cancels_running_loop():
    settings = Settings()
    entered = asyncio.Event()

    async def hang(_settings: Settings) -> None:
        entered.set()
        await asyncio.Event().wait()

    await periodic.start_periodic(
        name="cancel-me",
        interval_seconds=60,
        enabled=True,
        cycle=hang,
        settings=settings,
    )
    await asyncio.wait_for(entered.wait(), timeout=1)
    await periodic.stop_periodic("cancel-me")
    assert "cancel-me" not in periodic._tasks


def test_lock_ttl_conventions():
    assert periodic.lock_ttl_hold_across_ticks(60) == 600
    assert periodic.lock_ttl_yield_next_tick(900) == 870
    assert periodic.lock_ttl_yield_next_tick(40) == 60
    assert periodic.lock_ttl_yield_next_tick(900) < 900
