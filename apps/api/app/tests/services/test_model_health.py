"""Model health: one Redis round trip per read or write, and a breaker that half-opens."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest

from app.core.config import Settings
from app.services import model_health
from app.services.model_health import HealthSample

_SETTINGS = Settings(model_health_cooldown_seconds=30)


def _redis() -> Any:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


class _CountingRedis:
    """A fake Redis that counts round trips (a pipeline is one)."""

    def __init__(self) -> None:
        self.inner = _redis()
        self.round_trips = 0

    def pipeline(self, transaction: bool = True) -> Any:
        pipe = self.inner.pipeline(transaction=transaction)
        execute = pipe.execute

        async def counted() -> Any:
            self.round_trips += 1
            return await execute()

        pipe.execute = counted
        return pipe


async def _store(redis: Any, alias: str, *samples: tuple[bool, int, float]) -> None:
    """Samples with their own timestamps: (ok, latency ms, recorded at)."""
    key = f"recall:model_health:samples:{alias}"
    for ok, ms, at in samples:
        await redis.zadd(key, {f"{int(ok)}|{ms}|{int(at * 1e9)}": at})


async def _health(redis: Any, alias: str) -> model_health.ModelHealthSnapshot:
    return (await model_health.enrich_models_health(redis, _SETTINGS, [alias]))[alias]


@pytest.mark.asyncio
async def test_no_samples_is_healthy() -> None:
    snap = await _health(_redis(), "free-chat")
    assert snap.healthy is True
    assert snap.latency_p50_ms is None
    assert snap.sample_count == 0


@pytest.mark.asyncio
async def test_record_and_p50() -> None:
    redis = _redis()
    await model_health.record_samples(
        redis, [HealthSample("free-chat", latency_ms=ms, success=True) for ms in (100, 200, 300)]
    )
    snap = await _health(redis, "free-chat")
    assert snap.sample_count == 3
    assert snap.healthy is True
    assert snap.latency_p50_ms == 200


@pytest.mark.asyncio
async def test_a_failing_model_opens() -> None:
    redis = _redis()
    now = time.time()
    await _store(
        redis, "smart-chat", (True, 50, now - 4), *[(False, 50, now - i) for i in (3, 2, 1)]
    )
    snap = await _health(redis, "smart-chat")
    assert snap.sample_count == 4
    assert snap.error_rate == 0.75
    assert snap.healthy is False


@pytest.mark.asyncio
async def test_a_model_that_just_answered_is_closed() -> None:
    redis = _redis()
    now = time.time()
    await _store(
        redis, "smart-chat", *[(False, 50, now - i) for i in (4, 3, 2)], (True, 50, now - 1)
    )
    assert (await _health(redis, "smart-chat")).healthy is True


@pytest.mark.asyncio
async def test_a_provider_that_is_slow_to_start_counts_as_failing() -> None:
    redis = _redis()
    now = time.time()
    await _store(
        redis, "glm-5.2", (True, 800, now - 3), (True, 31_000, now - 2), (True, 32_000, now)
    )
    assert (await _health(redis, "glm-5.2")).healthy is False


@pytest.mark.asyncio
async def test_every_model_is_read_in_one_round_trip() -> None:
    redis = _CountingRedis()
    aliases = [
        "free-chat",
        "smart-chat",
        "glm-5.3-flash",
        "glm-5.2",
        "gpt-6-luna",
        "qwen-3.7-flash",
    ]
    found = await model_health.unhealthy_aliases(redis, _SETTINGS, aliases)  # type: ignore[arg-type]
    assert found == frozenset()
    assert redis.round_trips == 1


@pytest.mark.asyncio
async def test_a_turns_samples_are_written_in_one_round_trip() -> None:
    redis = _CountingRedis()
    await model_health.record_samples(
        redis,  # type: ignore[arg-type]
        [
            HealthSample("smart-chat", latency_ms=4000, success=False),
            HealthSample("glm-5.2", latency_ms=700, success=True),
        ],
    )
    assert redis.round_trips == 1
    assert (await _health(redis.inner, "smart-chat")).error_rate == 1.0
    assert (await _health(redis.inner, "glm-5.2")).healthy is True


@pytest.mark.asyncio
async def test_record_samples_swallows_redis_errors() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(side_effect=RuntimeError("down"))
    redis.pipeline.return_value = pipe
    await model_health.record_samples(redis, [HealthSample("free-chat", 10, success=True)])


@pytest.mark.asyncio
async def test_unreadable_health_is_all_healthy() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(side_effect=RuntimeError("down"))
    redis.pipeline.return_value = pipe
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, ["smart-chat"]) == frozenset()


@pytest.mark.asyncio
async def test_an_open_model_stays_open_through_its_cool_down() -> None:
    redis = _redis()
    now = time.time()
    await _store(redis, "smart-chat", (False, 50, now - 5))
    found = await model_health.unhealthy_aliases(redis, _SETTINGS, ["smart-chat", "glm-5.2"])
    assert found == frozenset({"smart-chat"})


@pytest.mark.asyncio
async def test_after_its_cool_down_one_turn_may_try_an_open_model() -> None:
    redis = _redis()
    await _store(redis, "smart-chat", (False, 50, time.time() - 31))
    aliases = ["smart-chat", "glm-5.2"]
    # The first turn claims the probe and may use it; the next still skips it.
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, aliases) == frozenset()
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, aliases) == {"smart-chat"}


@pytest.mark.asyncio
async def test_the_probe_decides_the_breaker() -> None:
    redis = _redis()
    await _store(redis, "smart-chat", (False, 50, time.time() - 31))
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, ["smart-chat"]) == frozenset()
    # The probe failed: open again, for a fresh cool-down.
    await model_health.record_samples(redis, [HealthSample("smart-chat", 3000, success=False)])
    await redis.delete("recall:model_health:probe:smart-chat")
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, ["smart-chat"]) == {"smart-chat"}
    # A later probe answered: closed for every turn.
    await model_health.record_samples(redis, [HealthSample("smart-chat", 600, success=True)])
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, ["smart-chat"]) == frozenset()
    assert await model_health.unhealthy_aliases(redis, _SETTINGS, ["smart-chat"]) == frozenset()


@pytest.mark.asyncio
async def test_enrich_models_health() -> None:
    redis = _redis()
    await model_health.record_samples(redis, [HealthSample("a", 40, success=True)])
    out = await model_health.enrich_models_health(redis, _SETTINGS, ["a", "b"])
    assert out["a"].sample_count == 1
    assert out["b"].sample_count == 0
