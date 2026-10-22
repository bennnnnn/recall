"""Model health: one sample per attempted alias, a recent window, and recovery."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways.litellm_gateway import StreamAttempt
from app.services import model_health


@pytest.fixture(autouse=True)
def _no_verdict_cache():
    model_health.forget_verdicts()
    yield
    model_health.forget_verdicts()


async def _samples(
    redis: Any, alias: str, *outcomes: tuple[bool, float], now: float | None = None
) -> None:
    await model_health.record_attempts(
        redis,
        [StreamAttempt(alias=alias, ok=ok, first_content_ms=ms) for ok, ms in outcomes],
        now=now,
    )


async def test_get_health_empty_is_healthy(fake_redis: Any) -> None:
    snap = await model_health.get_health(fake_redis, "free-chat")
    assert snap.healthy is True
    assert snap.latency_p50_ms is None
    assert snap.sample_count == 0


async def test_record_and_p50_of_time_to_first_content(fake_redis: Any) -> None:
    await _samples(fake_redis, "free-chat", (True, 100), (True, 200), (True, 300))
    snap = await model_health.get_health(fake_redis, "free-chat")
    assert snap.sample_count == 3
    assert snap.healthy is True
    assert snap.latency_p50_ms == 200


async def test_high_error_rate_unhealthy(fake_redis: Any) -> None:
    await _samples(fake_redis, "smart-chat", (True, 50), (False, 50), (False, 50), (False, 50))
    snap = await model_health.get_health(fake_redis, "smart-chat")
    assert snap.sample_count == 4
    assert snap.error_rate == 0.75
    assert snap.healthy is False


async def test_one_failure_is_not_an_outage(fake_redis: Any) -> None:
    await _samples(fake_redis, "smart-chat", (False, 8_000))
    assert (await model_health.get_health(fake_redis, "smart-chat")).healthy is True


async def test_a_long_healthy_reply_is_not_slow(fake_redis: Any) -> None:
    """Whole-reply time read as latency: a 60 s answer marked its model slow for a day."""
    await _samples(fake_redis, "smart-chat", (True, 900), (True, 1_100), (True, 1_000))
    assert (await model_health.get_health(fake_redis, "smart-chat")).healthy is True


async def test_an_alias_with_only_old_failures_is_routable_again(fake_redis: Any) -> None:
    """Unhealthy aliases get no new samples; the window lets them come back (half-open)."""
    an_hour_ago = time.time() - 3_600
    await _samples(fake_redis, "smart-chat", (False, 50), (False, 50), (False, 50), now=an_hour_ago)
    assert await model_health.unhealthy_aliases(fake_redis, MagicMock(), ["smart-chat"]) == (
        frozenset()
    )


async def test_the_verdict_is_shared_for_a_few_seconds(fake_redis: Any) -> None:
    await _samples(fake_redis, "a", (False, 50), (False, 50), (False, 50))
    assert await model_health.unhealthy_aliases(fake_redis, MagicMock(), ["a"]) == {"a"}
    with patch.object(fake_redis, "pipeline", side_effect=AssertionError("re-read")):
        assert await model_health.unhealthy_aliases(fake_redis, MagicMock(), ["a"]) == {"a"}


async def test_record_attempts_swallows_redis_errors() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=None)
    pipe.execute = AsyncMock(side_effect=RuntimeError("down"))
    redis.pipeline.return_value = pipe
    await model_health.record_attempts(redis, [StreamAttempt("free-chat", True, 10)])


async def test_enrich_models_health(fake_redis: Any) -> None:
    await _samples(fake_redis, "a", (True, 40))
    out = await model_health.enrich_models_health(fake_redis, MagicMock(), ["a", "b"])
    assert out["a"].sample_count == 1
    assert out["b"].sample_count == 0
