"""Rolling model health samples in Redis: a breaker per model (best-effort, never blocks chat).

Every model call of a turn leaves one sample: whether that model answered, and how
long its provider took to start (``latency_ms``). Samples are kept per provider
model, so aliases that run the same model share one breaker. A model is open, so
routing and fallbacks skip it, while half or more of its recent samples are bad
(failed, or slower than ``_SLOW_MS`` to start) and its newest one is bad too. Once
its cool-down has passed with no new sample it is half-open: routing may pick it
again, and a turn about to try it first claims its probe (``claim_probe``), so one
turn at a time tries it. A success closes the breaker, a failure opens it for
another cool-down.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.models import model_catalog

logger = logging.getLogger(__name__)

_SAMPLES_KEY = "recall:model_health:samples:{model}"
# Held by the one turn trying a half-open model; its sample lets the next one go.
_PROBE_KEY = "recall:model_health:probe:{model}"
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


@dataclass(frozen=True)
class Breakers:
    """The open models among those read, by alias."""

    # Inside their cool-down: routing and fallbacks skip them.
    cooling: frozenset[str] = frozenset()
    # Cool-down passed: a turn tries one only once it holds its probe.
    half_open: frozenset[str] = frozenset()


_NO_SAMPLES = ModelHealthSnapshot(healthy=True, latency_p50_ms=None, sample_count=0, error_rate=0.0)


def _model_of(alias: str) -> str:
    """The provider model whose breaker ``alias`` reads (an unknown alias is its own)."""
    if alias in model_catalog.known_ids():
        return model_catalog.get(alias).model
    return alias


def probe_ttl_seconds(settings: Settings) -> int:
    """How long a claimed probe stands: past the cool-down, and long enough for
    the probing turn to open its stream and wait out an idle provider."""
    attempt = settings.chat_stream_connect_timeout_seconds + settings.chat_stream_timeout_seconds
    return max(settings.model_health_cooldown_seconds, attempt)


async def record_samples(redis: Redis, samples: Sequence[HealthSample]) -> None:
    """Append a turn's samples in one round trip, and release their models' probes.

    Failures are logged and swallowed.
    """
    if not samples:
        return
    try:
        pipe = redis.pipeline(transaction=False)
        for sample in samples:
            model = _model_of(sample.alias)
            key = _SAMPLES_KEY.format(model=model)
            # score = timestamp; member encodes success|latency|unique
            member = f"{int(sample.success)}|{int(sample.latency_ms)}|{time.time_ns()}"
            pipe.zadd(key, {member: time.time()})
            pipe.zremrangebyrank(key, 0, -(_MAX_SAMPLES + 1))
            pipe.expire(key, _SAMPLE_TTL_SECONDS)
            # The sample decides the breaker; the next cool-down starts from it.
            pipe.delete(_PROBE_KEY.format(model=model))
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
    models = list(dict.fromkeys(_model_of(alias) for alias in aliases))
    try:
        pipe = redis.pipeline(transaction=False)
        for model in models:
            pipe.zrange(_SAMPLES_KEY.format(model=model), 0, -1, withscores=True)
        raw = await pipe.execute()
    except Exception:
        logger.debug("model health read failed", exc_info=True)
        return dict.fromkeys(aliases, _NO_SAMPLES)
    by_model = {model: _snapshot(samples) for model, samples in zip(models, raw, strict=True)}
    return {alias: by_model[_model_of(alias)] for alias in aliases}


async def read_breakers(redis: Redis, settings: Settings, aliases: list[str]) -> Breakers:
    """The open models among ``aliases``, cooling or half-open; none when health
    can't be read. Reading claims nothing: routing must never fail a turn over a
    health read, nor use up a probe for a model the turn does not try.
    """
    try:
        snaps = await enrich_models_health(redis, settings, aliases)
    except Exception:
        logger.debug("model health read failed during routing", exc_info=True)
        return Breakers()
    cooldown = settings.model_health_cooldown_seconds
    now = time.time()
    cooling: set[str] = set()
    half_open: set[str] = set()
    for alias, snap in snaps.items():
        if snap.healthy:
            continue
        cooled = snap.newest_at is not None and now - snap.newest_at >= cooldown
        (half_open if cooled else cooling).add(alias)
    return Breakers(cooling=frozenset(cooling), half_open=frozenset(half_open))


async def claim_probe(redis: Redis, settings: Settings, alias: str) -> bool:
    """Claim the one try a half-open model allows; False when another turn holds it.

    Called right before a turn tries the model. A claim that can't be made counts
    as lost: without the record, every turn could pile onto a failing model.
    """
    try:
        key = _PROBE_KEY.format(model=_model_of(alias))
        return bool(await redis.set(key, "1", nx=True, ex=probe_ttl_seconds(settings)))
    except Exception:
        logger.debug("model health probe claim failed", exc_info=True)
        return False
