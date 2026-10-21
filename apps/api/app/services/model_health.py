"""Rolling model health samples in Redis: a breaker per model (best-effort, never blocks chat).

Every model call of a turn leaves one sample: whether that model answered, and how
long its provider took to start (``latency_ms``). A model is open, so routing and
fallbacks skip it, while half or more of its recent samples are bad (failed, or
slower than ``_SLOW_MS`` to start) and its newest one is bad too. Once its cool-down
has passed with no new sample, one turn may use it again (half-open): a success
closes the breaker, a failure opens it for another cool-down.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings

logger = logging.getLogger(__name__)

_SAMPLES_KEY = "recall:model_health:samples:{alias}"
# Held by the one turn that may try an open model again.
_PROBE_KEY = "recall:model_health:probe:{alias}"
_MAX_SAMPLES = 40
_SAMPLE_TTL_SECONDS = 86_400
# A provider this slow to start answering counts against its model.
_SLOW_MS = 30_000
_BAD_RATE = 0.5


@dataclass(frozen=True)
class HealthSample:
    """One model call: did that model answer, and how long until its provider started."""

    alias: str
    latency_ms: float
    success: bool


@dataclass(frozen=True)
class ModelHealthSnapshot:
    healthy: bool
    latency_p50_ms: int | None
    sample_count: int
    error_rate: float
    # When the newest sample was recorded (epoch seconds); None without samples.
    newest_at: float | None = None


_NO_SAMPLES = ModelHealthSnapshot(healthy=True, latency_p50_ms=None, sample_count=0, error_rate=0.0)


async def record_samples(redis: Redis, samples: Sequence[HealthSample]) -> None:
    """Append a turn's samples in one round trip. Failures are logged and swallowed."""
    if not samples:
        return
    try:
        pipe = redis.pipeline(transaction=False)
        for sample in samples:
            key = _SAMPLES_KEY.format(alias=sample.alias)
            # score = timestamp; member encodes success|latency|unique
            member = f"{int(sample.success)}|{int(sample.latency_ms)}|{time.time_ns()}"
            pipe.zadd(key, {member: time.time()})
            pipe.zremrangebyrank(key, 0, -(_MAX_SAMPLES + 1))
            pipe.expire(key, _SAMPLE_TTL_SECONDS)
        await pipe.execute()
    except Exception:
        logger.debug("model health samples failed", exc_info=True)


def _parse(raw: Iterable[Any]) -> list[tuple[bool, int, float]]:
    """(ok, latency ms, recorded at) per stored sample, oldest first."""
    samples: list[tuple[bool, int, float]] = []
    for item in raw:
        member, score = item if isinstance(item, tuple | list) else (item, None)
        text = member.decode() if isinstance(member, bytes) else str(member)
        parts = text.split("|")
        try:
            # The score is when it was recorded; the member's last part is too.
            at = float(score) if score is not None else int(parts[2]) / 1e9
            samples.append((parts[0] == "1", int(parts[1]), at))
        except (ValueError, IndexError):
            continue
    return sorted(samples, key=lambda sample: sample[2])


def _snapshot(raw: Iterable[Any]) -> ModelHealthSnapshot:
    samples = _parse(raw)
    if not samples:
        return _NO_SAMPLES
    bad = [not ok or ms >= _SLOW_MS for ok, ms, _at in samples]
    errors = sum(1 for ok, _ms, _at in samples if not ok)
    latencies = sorted(ms for ok, ms, _at in samples if ok)
    return ModelHealthSnapshot(
        # A model that just answered is closed, whatever came before.
        healthy=not (bad[-1] and sum(bad) / len(bad) >= _BAD_RATE),
        latency_p50_ms=latencies[len(latencies) // 2] if latencies else None,
        sample_count=len(samples),
        error_rate=errors / len(samples),
        newest_at=samples[-1][2],
    )


async def enrich_models_health(
    redis: Redis,
    settings: Settings,
    aliases: list[str],
) -> dict[str, ModelHealthSnapshot]:
    """Every alias's breaker in one Redis round trip; all healthy when it can't be read."""
    _ = settings
    if not aliases:
        return {}
    try:
        pipe = redis.pipeline(transaction=False)
        for alias in aliases:
            pipe.zrange(_SAMPLES_KEY.format(alias=alias), 0, -1, withscores=True)
        raw = await pipe.execute()
    except Exception:
        logger.debug("model health read failed", exc_info=True)
        return dict.fromkeys(aliases, _NO_SAMPLES)
    return {alias: _snapshot(samples) for alias, samples in zip(aliases, raw, strict=True)}


async def _claim_probes(redis: Redis, aliases: list[str], ttl_seconds: int) -> set[str]:
    """The open models this turn may try again: each goes to one turn per cool-down."""
    if not aliases:
        return set()
    try:
        pipe = redis.pipeline(transaction=False)
        for alias in aliases:
            pipe.set(_PROBE_KEY.format(alias=alias), "1", nx=True, ex=ttl_seconds)
        claimed = await pipe.execute()
    except Exception:
        logger.debug("model health probe claim failed", exc_info=True)
        return set()
    return {alias for alias, won in zip(aliases, claimed, strict=True) if won}


async def unhealthy_aliases(redis: Redis, settings: Settings, aliases: list[str]) -> frozenset[str]:
    """The aliases whose breaker is open; empty when health can't be read.

    An open model whose cool-down has passed is left out for the one turn that
    claims its probe, so that turn can try it. Best-effort: routing must never
    fail a turn over a health read.
    """
    try:
        snaps = await enrich_models_health(redis, settings, aliases)
    except Exception:
        logger.debug("model health read failed during routing", exc_info=True)
        return frozenset()
    open_models = [alias for alias, snap in snaps.items() if not snap.healthy]
    cooldown = settings.model_health_cooldown_seconds
    now = time.time()
    cooled = [
        alias
        for alias in open_models
        if (newest := snaps[alias].newest_at) is not None and now - newest >= cooldown
    ]
    probing = await _claim_probes(redis, cooled, cooldown)
    return frozenset(alias for alias in open_models if alias not in probing)
