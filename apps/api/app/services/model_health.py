"""Rolling model health samples in Redis (best-effort, never blocks chat)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import Settings

logger = logging.getLogger(__name__)

_SAMPLES_KEY = "recall:model_health:samples:{alias}"
_MAX_SAMPLES = 40
_SAMPLE_TTL_SECONDS = 86_400


@dataclass(frozen=True)
class ModelHealthSnapshot:
    healthy: bool
    latency_p50_ms: int | None
    sample_count: int
    error_rate: float


async def record_sample(
    redis: Redis,
    alias: str,
    *,
    latency_ms: float,
    success: bool,
) -> None:
    """Append one sample. Failures are logged and swallowed."""
    try:
        key = _SAMPLES_KEY.format(alias=alias)
        # score = timestamp; member encodes success|latency
        member = f"{int(success)}|{int(latency_ms)}|{time.time_ns()}"
        pipe = redis.pipeline()
        pipe.zadd(key, {member: time.time()})
        pipe.zremrangebyrank(key, 0, -(_MAX_SAMPLES + 1))
        pipe.expire(key, _SAMPLE_TTL_SECONDS)
        await pipe.execute()
    except Exception:
        logger.debug("model health sample failed alias=%s", alias, exc_info=True)


async def get_health(redis: Redis, alias: str) -> ModelHealthSnapshot:
    try:
        key = _SAMPLES_KEY.format(alias=alias)
        raw = await redis.zrange(key, 0, -1)
    except Exception:
        logger.debug("model health read failed alias=%s", alias, exc_info=True)
        return ModelHealthSnapshot(
            healthy=True, latency_p50_ms=None, sample_count=0, error_rate=0.0
        )

    samples: list[tuple[bool, int]] = []
    for item in raw:
        text = item.decode() if isinstance(item, bytes) else str(item)
        parts = text.split("|")
        if len(parts) < 2:
            continue
        try:
            samples.append((parts[0] == "1", int(parts[1])))
        except ValueError:
            continue

    if not samples:
        return ModelHealthSnapshot(
            healthy=True, latency_p50_ms=None, sample_count=0, error_rate=0.0
        )

    errors = sum(1 for ok, _ in samples if not ok)
    error_rate = errors / len(samples)
    latencies = sorted(ms for ok, ms in samples if ok)
    p50 = latencies[len(latencies) // 2] if latencies else None
    healthy = error_rate < 0.5 and (p50 is None or p50 < 30_000)
    return ModelHealthSnapshot(
        healthy=healthy,
        latency_p50_ms=p50,
        sample_count=len(samples),
        error_rate=error_rate,
    )


async def enrich_models_health(
    redis: Redis,
    settings: Settings,
    aliases: list[str],
) -> dict[str, ModelHealthSnapshot]:
    _ = settings
    snaps = await asyncio.gather(*(get_health(redis, alias) for alias in aliases))
    return dict(zip(aliases, snaps, strict=True))
