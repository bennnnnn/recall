"""Live talk minutes (a monthly allowance per plan).

Live talk runs phone <-> OpenAI over WebRTC once the server mints a session,
so the server meters time at its own boundary: mint reserves a capped
session length out of this UTC month's seconds, and the end report settles
it to the time that actually passed (never refunding past the reservation).
A phone that never reports keeps the full reservation charged.
"""

import logging
import math
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.modules.billing.entitlements import allowance
from app.services.quota.counters import refund_daily

logger = logging.getLogger(__name__)

# A month counter outlives its month long enough for a late settle, then expires.
MONTHLY_TTL = 60 * 60 * 24 * 40
# A reservation waits this long past its session for the phone's end report.
_LIVE_TALK_SETTLE_GRACE_SECONDS = 15 * 60


def utc_month(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def next_month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if current.month == 12:
        return datetime(current.year + 1, 1, 1, tzinfo=UTC)
    return datetime(current.year, current.month + 1, 1, tzinfo=UTC)


def live_talk_month_key(user_id: UUID, month: str) -> str:
    return f"livetalk_sec:{user_id}:{month}"


def _live_talk_reservation_key(user_id: UUID, session_id: str) -> str:
    return f"livetalk_res:{user_id}:{session_id}"


def live_talk_allowance_seconds(user: User, settings: Settings) -> int:
    return allowance(user, "monthly_live_talk_minutes", settings) * 60


async def live_talk_used_seconds(redis: Redis, user_id: UUID, *, month: str | None = None) -> int:
    value = await redis.get(live_talk_month_key(user_id, month or utc_month()))
    return max(0, int(value or 0))


async def reserve_live_talk_seconds(
    redis: Redis,
    user_id: UUID,
    *,
    allowance_seconds: int,
    max_session_seconds: int,
    min_session_seconds: int,
) -> int:
    """Take up to one session's seconds from this month. 0 = refused.

    INCRBY-then-trim keeps parallel mints honest: whoever lands past the
    allowance gives the excess back, and drops out entirely when what is left
    for it is under the minimum session.
    """
    if allowance_seconds <= 0 or max_session_seconds <= 0:
        return 0
    floor = max(1, min_session_seconds)
    key = live_talk_month_key(user_id, utc_month())
    try:
        used = int(await redis.get(key) or 0)
        grant = min(max_session_seconds, allowance_seconds - used)
        if grant < floor:
            return 0
        total = await redis.incrby(key, grant)
        if total == grant:
            await redis.expire(key, MONTHLY_TTL)
        overshoot = total - allowance_seconds
        if overshoot > 0:
            if grant - overshoot < floor:
                await redis.incrby(key, -grant)
                return 0
            await redis.incrby(key, -overshoot)
            grant -= overshoot
        return grant
    except RedisError as exc:
        logger.warning(
            "Live talk reserve failed; Redis unavailable user=%s", user_id, exc_info=True
        )
        raise RedisUnavailableError() from exc


async def record_live_talk_reservation(
    redis: Redis, user_id: UUID, session_id: str, *, reserved_seconds: int
) -> None:
    started_ms = int(datetime.now(UTC).timestamp() * 1000)
    await redis.set(
        _live_talk_reservation_key(user_id, session_id),
        f"{reserved_seconds}:{started_ms}:{utc_month()}",
        ex=reserved_seconds + _LIVE_TALK_SETTLE_GRACE_SECONDS,
    )


async def release_live_talk_seconds(
    redis: Redis, user_id: UUID, *, seconds: int, month: str | None = None
) -> None:
    """Give back seconds that were reserved but never became a session."""
    if seconds <= 0:
        return
    await refund_daily(redis, live_talk_month_key(user_id, month or utc_month()), amount=seconds)


async def settle_live_talk_session(redis: Redis, user_id: UUID, session_id: str) -> int | None:
    """Charge the time that passed since mint; refund the rest of the reservation.

    Returns the seconds charged, or None when there is nothing to settle (an
    unknown session, a second report, or one that came after the grace window,
    which keeps the full reservation). The server's clock decides: a phone
    cannot shorten its own session by reporting less.
    """
    raw = await redis.getdel(_live_talk_reservation_key(user_id, (session_id or "").strip()))
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes | bytearray) else str(raw)
    try:
        reserved_text, started_text, month = text.split(":", 2)
        reserved = int(reserved_text)
        started_ms = int(started_text)
    except ValueError:
        return None
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    elapsed = math.ceil(max(0, now_ms - started_ms) / 1000)
    charged = min(reserved, elapsed)
    await release_live_talk_seconds(redis, user_id, seconds=reserved - charged, month=month)
    return charged
