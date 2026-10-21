"""Rolling model health samples in Redis (best-effort, never blocks chat)."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import mock_llm
from app.models.model_catalog import ChatModel

logger = logging.getLogger(__name__)

_SAMPLES_KEY = "recall:model_health:samples:{alias}"
_MAX_SAMPLES = 40
_SAMPLE_TTL_SECONDS = 86_400
# Only samples this recent count. An unhealthy alias leaves Auto and the fallbacks, so
# it gets no new samples: once its failures age out it is routable again (half-open).
_WINDOW_SECONDS = 15 * 60
# Fewer samples than this never mark an alias unhealthy: one blip is not an outage.
_MIN_SAMPLES = 3
# Time to first content past this, at the median, is too slow to route to.
_SLOW_FIRST_CONTENT_MS = 30_000
# The verdict is shared by every turn on this process for a few seconds: six ZRANGEs
# per turn for a best-effort hint was most of a turn's Redis traffic.
_VERDICT_CACHE_SECONDS = 3.0
_verdicts: dict[tuple[str, ...], tuple[float, frozenset[str]]] = {}


class _Attempt(Protocol):
    @property
    def alias(self) -> str: ...

    @property
    def ok(self) -> bool: ...

    @property
    def first_content_ms(self) -> float: ...


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
    """Append one sample (``latency_ms`` = time to first content). Failures are swallowed."""
    await record_attempts(redis, [_Sample(alias, success, latency_ms)])


@dataclass(frozen=True, slots=True)
class _Sample:
    alias: str
    ok: bool
    first_content_ms: float


async def record_attempts(redis: Redis, attempts: Sequence[_Attempt]) -> None:
    """One sample per alias a stream tried, in one round trip. Failures are swallowed."""
    if not attempts:
        return
    try:
        now = time.time()
        async with redis.pipeline(transaction=False) as pipe:
            for attempt in attempts:
                key = _SAMPLES_KEY.format(alias=attempt.alias)
                # score = timestamp; member encodes success|latency|nonce
                member = f"{int(attempt.ok)}|{int(attempt.first_content_ms)}|{time.time_ns()}"
                pipe.zadd(key, {member: now})
                pipe.zremrangebyrank(key, 0, -(_MAX_SAMPLES + 1))
                pipe.expire(key, _SAMPLE_TTL_SECONDS)
            await pipe.execute()
    except Exception:
        logger.debug("model health samples failed", exc_info=True)


def _snapshot(raw: Sequence[object]) -> ModelHealthSnapshot:
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
    enough = len(samples) >= _MIN_SAMPLES
    healthy = not enough or (error_rate < 0.5 and (p50 is None or p50 < _SLOW_FIRST_CONTENT_MS))
    return ModelHealthSnapshot(
        healthy=healthy,
        latency_p50_ms=p50,
        sample_count=len(samples),
        error_rate=error_rate,
    )


async def _read_windows(redis: Redis, aliases: Sequence[str]) -> list[list[object]]:
    since = time.time() - _WINDOW_SECONDS
    async with redis.pipeline(transaction=False) as pipe:
        for alias in aliases:
            pipe.zrangebyscore(_SAMPLES_KEY.format(alias=alias), since, "+inf")
        return list(await pipe.execute())


async def get_health(redis: Redis, alias: str) -> ModelHealthSnapshot:
    return (await enrich_models_health(redis, None, [alias]))[alias]


async def enrich_models_health(
    redis: Redis,
    settings: Settings | None,
    aliases: list[str],
) -> dict[str, ModelHealthSnapshot]:
    """Each alias's health over the last ``_WINDOW_SECONDS``; healthy when unreadable."""
    _ = settings
    try:
        windows = await _read_windows(redis, aliases)
    except Exception:
        logger.debug("model health read failed", exc_info=True)
        windows = [[] for _ in aliases]
    return {alias: _snapshot(raw) for alias, raw in zip(aliases, windows, strict=True)}


async def unhealthy_aliases(redis: Redis, settings: Settings, aliases: list[str]) -> frozenset[str]:
    """The aliases whose provider is failing or slow; empty when health can't be read.

    Best-effort: routing must never fail a turn over a health read. Shared per process
    for ``_VERDICT_CACHE_SECONDS``.
    """
    key = tuple(aliases)
    cached = _verdicts.get(key)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]
    try:
        snaps = await enrich_models_health(redis, settings, aliases)
    except Exception:
        logger.debug("model health read failed during routing", exc_info=True)
        return frozenset()
    verdict = frozenset(alias for alias, snap in snaps.items() if not snap.healthy)
    _verdicts[key] = (now + _VERDICT_CACHE_SECONDS, verdict)
    return verdict


def forget_verdicts() -> None:
    """Drop the per-process verdict cache (tests)."""
    _verdicts.clear()


def is_available(model: ChatModel, settings: Settings) -> bool:
    """Whether this process can serve ``model``: mock mode, or its provider key is set."""
    if mock_llm.should_mock_llm(settings):
        return True
    return bool(getattr(settings, model.api_key_field, ""))
