"""The daily token budget: reserve before a turn, settle after, heal from the DB."""

import logging
from datetime import date

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.modules.billing.entitlements import allowance
from app.services.quota.counters import (
    DAILY_TTL,
    daily_key,
    floor_counter,
    raise_counter,
    refund_daily,
    utc_today,
)

logger = logging.getLogger(__name__)


def _usage_key(user_id: str, day: date) -> str:
    return daily_key("usage", user_id, day)


def _heal_flag_key(user_id: str, day: date) -> str:
    return daily_key("usage:heal", user_id, day)


def daily_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_tokens", settings)


async def get_daily_usage(redis: Redis, user_id: str) -> int:
    key = _usage_key(user_id, utc_today())
    value = await redis.get(key)
    return int(value or 0)


async def has_daily_usage_key(redis: Redis, user_id: str, *, day: date | None = None) -> bool:
    """True when today's Redis usage counter already exists (seed is a no-op)."""
    return bool(await redis.exists(_usage_key(user_id, day or utc_today())))


async def seed_usage_if_missing(
    redis: Redis,
    user_id: str,
    db_total: int,
    *,
    day: date | None = None,
) -> None:
    """Self-heal the Redis daily counter after a flush/eviction.

    If the Redis key for today is absent, seed it with the DB-recorded total so
    quota enforcement resumes from the correct baseline instead of resetting to
    zero. Uses SET NX so concurrent calls (e.g. overlapping turns) can't
    double-count, and never overwrites a live counter. No-op when db_total <= 0.
    """
    if db_total <= 0:
        return
    key = _usage_key(user_id, day or utc_today())
    await redis.set(key, db_total, nx=True, ex=DAILY_TTL)


async def mark_usage_needs_heal(
    redis: Redis,
    user_id: str,
    *,
    day: date | None = None,
) -> None:
    """Remember that post-commit ``adjust_usage`` failed so the next turn can heal."""
    try:
        await redis.set(_heal_flag_key(user_id, day or utc_today()), "1", ex=DAILY_TTL)
    except RedisError:
        logger.warning("mark_usage_needs_heal failed user_id=%s", user_id, exc_info=True)


async def usage_needs_heal(
    redis: Redis,
    user_id: str,
    *,
    day: date | None = None,
) -> bool:
    try:
        return bool(await redis.exists(_heal_flag_key(user_id, day or utc_today())))
    except RedisError:
        logger.warning("usage_needs_heal failed user_id=%s", user_id, exc_info=True)
        return False


async def clear_usage_needs_heal(
    redis: Redis,
    user_id: str,
    *,
    day: date | None = None,
) -> None:
    try:
        await redis.delete(_heal_flag_key(user_id, day or utc_today()))
    except RedisError:
        logger.warning("clear_usage_needs_heal failed user_id=%s", user_id, exc_info=True)


async def heal_usage_drift(
    redis: Redis,
    user_id: str,
    db_total: int,
    *,
    day: date | None = None,
) -> None:
    """Heal Redis/DB drift when Redis holds a stale value lower than the DB.

    ``seed_usage_if_missing`` only seeds when the key is absent — if Redis
    holds a stale value *lower* than the DB total (repeated ``adjust_usage``
    failures, partial outages, manual key edits), seeding is skipped forever
    for that UTC day and the user can exceed daily limits. This compares the
    two and raises Redis to ``max(redis, db_total)`` when DB is ahead. Never
    lowers a live counter. Atomic via Lua; GET+SET fallback when EVAL is
    unavailable (some fakeredis setups).
    """
    if db_total <= 0:
        return
    key = _usage_key(user_id, day or utc_today())
    try:
        await raise_counter(redis, key, db_total, ttl=DAILY_TTL)
    except RedisError:
        logger.warning("heal_usage_drift failed user_id=%s", user_id, exc_info=True)
        raise


async def reserve_usage(
    redis: Redis,
    user_id: str,
    requested: int,
    *,
    daily_limit: int,
) -> bool:
    """Atomically reserve tokens before generation. Refunds if over limit.

    Redis outages fail closed (``RedisUnavailableError``) — never skip the
    reserve and allow unbounded generation.
    """
    if requested <= 0:
        return True
    key = _usage_key(user_id, utc_today())
    try:
        new_total = await redis.incrby(key, requested)
        if new_total == requested:
            await redis.expire(key, DAILY_TTL)
        if new_total > daily_limit:
            # Roll back the over-limit reservation. If this incrby fails
            # (Redis blip after the first succeeded), the user would be
            # permanently charged for a turn that was rejected — retry once
            # so the charge doesn't stick.
            try:
                await redis.incrby(key, -requested)
            except RedisError:
                logger.warning(
                    "Quota over-limit rollback failed; retrying user_id=%s", user_id, exc_info=True
                )
                await redis.incrby(key, -requested)
            return False
        return True
    except RedisError as exc:
        logger.warning("Quota reserve failed; Redis unavailable user_id=%s", user_id, exc_info=True)
        raise RedisUnavailableError() from exc


async def refund_usage(redis: Redis, user_id: str, amount: int) -> None:
    if amount <= 0:
        return
    await refund_daily(redis, _usage_key(user_id, utc_today()), amount=amount)


async def adjust_usage(
    redis: Redis,
    user_id: str,
    reserved: int,
    actual: int,
    *,
    daily_limit: int | None = None,
) -> int:
    delta = actual - reserved
    if delta == 0:
        return await get_daily_usage(redis, user_id)
    return await record_usage(redis, user_id, delta, daily_limit=daily_limit)


async def record_usage(
    redis: Redis,
    user_id: str,
    tokens: int,
    *,
    daily_limit: int | None = None,
) -> int:
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, tokens)
    if new_total == tokens:
        await redis.expire(key, DAILY_TTL)
    if new_total < 0:
        await floor_counter(redis, key)
        new_total = 0
    # Cap overshoot: a single turn whose actual usage exceeds the reserve
    # estimate can push the daily counter past the limit. Clip at daily_limit
    # so one turn can't blow the cap (the over-limit tokens are forfeit —
    # they were genuinely used, but the counter must not exceed the limit
    # or subsequent reserve_usage checks under-report remaining quota).
    if daily_limit is not None and new_total > daily_limit:
        await redis.set(key, daily_limit, ex=DAILY_TTL)
        new_total = daily_limit
    return new_total


async def reset_daily_usage(redis: Redis, user_id: str, day: date | None = None) -> None:
    """Clear Redis quota counter for a user/day (dev support)."""
    await redis.delete(_usage_key(user_id, day or utc_today()))
