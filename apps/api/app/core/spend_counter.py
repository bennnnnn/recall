"""The global UTC-day spend counter: estimated provider dollars, in Redis.

Infrastructure, so the gateways can add what each model call cost; what the
cap stops and the fixed prices live in ``services/quota/spend.py``.

Integer micro-dollars (1e-6 USD) so INCRBY stays atomic, rounded UP so no
paid call ever records as free. The previous unit was 1e-3 USD with
round(): a typical $0.0002-0.0005 free-chat turn recorded 0, and the cap
never saw free-tier traffic. 0-limit settings are unlimited (dev/tests).
Redis errors fail closed, so nothing spends while the meter is blind, and say so:
``RedisUnavailableError``, never "the cap is reached".
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.readings import keep_for_turn, kept_for_turn
from app.core.redis_counters import incr_with_ttl
from app.exceptions import RedisUnavailableError

logger = logging.getLogger(__name__)

MICRO_USD_PER_USD = 1_000_000
# A day's counter outlives it long enough to read yesterday, then expires.
SPEND_KEY_TTL_SECONDS = 60 * 60 * 48


def spend_key(day: date | None = None) -> str:
    return f"spend_musd:{(day or datetime.now(UTC).date()).isoformat()}"


def usd_to_micro_usd(usd: float) -> int:
    if usd <= 0:
        return 0
    # round() first strips float noise (0.0004 * 1e6 = 400.00000000000006).
    return max(1, math.ceil(round(usd * MICRO_USD_PER_USD, 6)))


async def record_global_spend(redis: Redis, usd: float, *, day: date | None = None) -> int:
    """Add estimated dollars to the global spend counter (today's unless *day*).

    Returns that day's total in micro-USD.
    """
    amount = usd_to_micro_usd(usd)
    if amount <= 0:
        return await get_global_spend_micro_usd(redis)
    return await incr_with_ttl(redis, spend_key(day), amount, SPEND_KEY_TTL_SECONDS)


async def get_global_spend_micro_usd(redis: Redis) -> int:
    """Today's spend in micro-USD (every chat turn reads it).

    The pre-fix ``spend_mcents`` key lost its writer on 2026-10-15; its read missed
    every time after that and cost every model-calling path a command."""
    return int(await redis.get(spend_key()) or 0)


async def global_spend_exceeded(redis: Redis, settings: Settings) -> bool:
    """True when today's spend is at/over the cap (a cap of 0 is none).

    Redis down raises ``RedisUnavailableError`` (fail closed): a request answers 503
    unavailable, the chat its ``unavailable`` frame. It returned True, so an outage after
    sign-in said the day's cap was reached: pictures, scans, voice and memory edits
    "paused", chat "at capacity for today". Work nobody waits on skips on either.
    """
    if settings.daily_global_spend_usd <= 0:
        return False
    limit = usd_to_micro_usd(settings.daily_global_spend_usd)
    try:
        return await _spend_this_turn(redis) >= limit
    except RedisError as exc:
        logger.warning("Global spend check failed; failing closed as unavailable", exc_info=True)
        raise RedisUnavailableError() from exc


# The turn's one read of today's spend (``core.readings.keep_for_turn``).
_TURN_SPEND_READ = "global_spend_read"
# How long a turn's checks share one read: the reads a turn starts together (its admission,
# live read, figure, chart and formal reads) share it; a later check (the tool loop after
# the prompt is built, the follow-ups and jobs after the reply) reads again, so a cap
# crossed mid-turn, or Redis failing, stops the turn's extras as docs/PRODUCTION.md says
# (review of #2592).
TURN_SPEND_SHARED_SECONDS = 1.0


def _monotonic() -> float:
    return time.monotonic()


async def _spend_this_turn(redis: Redis) -> int:
    """Today's spend, one read for the checks a chat turn makes together: its admission and
    the reads it starts beside the reply each read the same key, about six GETs a turn
    (audit, 2026-11-25). A check more than ``TURN_SPEND_SHARED_SECONDS`` after the turn's
    read reads again; outside a turn (a job, an HTTP request) each check reads it."""
    kept = kept_for_turn(_TURN_SPEND_READ)
    now = _monotonic()
    if kept is None or now - kept[0] > TURN_SPEND_SHARED_SECONDS:
        kept = (now, asyncio.ensure_future(get_global_spend_micro_usd(redis)))
        keep_for_turn(_TURN_SPEND_READ, kept)
    # Shielded: a caller that is stopped never cancels the read the others wait on.
    spent: int = await asyncio.shield(kept[1])
    return spent


SpendCheck = Callable[[Redis, Settings], Awaitable[bool]]


async def spend_pause_reason(check: SpendCheck, redis: Redis, settings: Settings) -> str | None:
    """Why work nobody waits on (a background job, a turn's tools) skips now: the day's cap
    reached, or the spend unreadable (Redis down), where it fails closed; None when it may
    run. ``check`` is ``global_spend_exceeded`` as the caller reaches it. The one rule
    three callers each wrote (audit, 2026-11-25)."""
    try:
        return "global spend cap" if await check(redis, settings) else None
    except RedisUnavailableError:
        return "global spend unreadable (Redis down)"
