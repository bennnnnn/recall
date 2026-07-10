"""Unit tests for Redis-backed model health samples."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import model_health


class _FakeRedis:
    def __init__(self) -> None:
        self._zsets: dict[str, dict[str, float]] = {}

    def pipeline(self) -> _FakePipe:
        return _FakePipe(self)

    async def zrange(self, key: str, start: int, end: int) -> list[str]:
        items = sorted(self._zsets.get(key, {}).items(), key=lambda kv: kv[1])
        members = [m for m, _ in items]
        if end == -1:
            return members[start:]
        return members[start : end + 1]


class _FakePipe:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[Any, ...]] = []

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self._ops.append(("zadd", key, mapping))

    def zremrangebyrank(self, key: str, start: int, end: int) -> None:
        self._ops.append(("zremrangebyrank", key, start, end))

    def expire(self, key: str, ttl: int) -> None:
        self._ops.append(("expire", key, ttl))

    async def execute(self) -> list[Any]:
        for op in self._ops:
            if op[0] == "zadd":
                _, key, mapping = op
                bucket = self._redis._zsets.setdefault(key, {})
                bucket.update(mapping)
            elif op[0] == "zremrangebyrank":
                _, key, start, end = op
                items = sorted(self._redis._zsets.get(key, {}).items(), key=lambda kv: kv[1])
                # Redis: remove by rank inclusive; negative end from end
                if end < 0:
                    keep_from = len(items) + end + 1
                    if keep_from < 0:
                        keep_from = 0
                    kept = items[keep_from:]
                else:
                    kept = [it for i, it in enumerate(items) if not (start <= i <= end)]
                self._redis._zsets[key] = dict(kept)
        self._ops.clear()
        return []


@pytest.mark.asyncio
async def test_get_health_empty_is_healthy() -> None:
    redis = _FakeRedis()
    snap = await model_health.get_health(redis, "free-chat")  # type: ignore[arg-type]
    assert snap.healthy is True
    assert snap.latency_p50_ms is None
    assert snap.sample_count == 0


@pytest.mark.asyncio
async def test_record_and_p50() -> None:
    redis = _FakeRedis()
    for ms in (100, 200, 300):
        await model_health.record_sample(redis, "free-chat", latency_ms=ms, success=True)  # type: ignore[arg-type]
    snap = await model_health.get_health(redis, "free-chat")  # type: ignore[arg-type]
    assert snap.sample_count == 3
    assert snap.healthy is True
    assert snap.latency_p50_ms == 200


@pytest.mark.asyncio
async def test_high_error_rate_unhealthy() -> None:
    redis = _FakeRedis()
    await model_health.record_sample(redis, "smart-chat", latency_ms=50, success=True)  # type: ignore[arg-type]
    for _ in range(3):
        await model_health.record_sample(redis, "smart-chat", latency_ms=50, success=False)  # type: ignore[arg-type]
    snap = await model_health.get_health(redis, "smart-chat")  # type: ignore[arg-type]
    assert snap.sample_count == 4
    assert snap.error_rate == 0.75
    assert snap.healthy is False


@pytest.mark.asyncio
async def test_record_sample_swallows_redis_errors() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.zadd = MagicMock()
    pipe.zremrangebyrank = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(side_effect=RuntimeError("down"))
    redis.pipeline.return_value = pipe
    await model_health.record_sample(redis, "free-chat", latency_ms=10, success=True)


@pytest.mark.asyncio
async def test_enrich_models_health() -> None:
    redis = _FakeRedis()
    await model_health.record_sample(redis, "a", latency_ms=40, success=True)  # type: ignore[arg-type]
    settings = MagicMock()
    out = await model_health.enrich_models_health(redis, settings, ["a", "b"])  # type: ignore[arg-type]
    assert out["a"].sample_count == 1
    assert out["b"].sample_count == 0
