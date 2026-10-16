"""Per-user daily counters in Redis, and the table of per-feature daily caps."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.modules.billing.entitlements import Allowance, allowance
from app.services.quota.messages import (
    IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE,
    IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PAID,
    IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE,
    IMAGE_LIMIT_EXCEEDED_MESSAGE_PAID,
    IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_FREE,
    IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_PAID,
    SPEECH_LIMIT_EXCEEDED_MESSAGE,
    SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE,
    plan_message,
)

logger = logging.getLogger(__name__)


def utc_today() -> date:
    return datetime.now(UTC).date()


def daily_key(prefix: str, owner: str | UUID, day: date | None = None) -> str:
    """Per-user, per-UTC-day counter key shared by every daily cap."""
    return f"{prefix}:{owner}:{(day or utc_today()).isoformat()}"


# Daily counters outlive their day by enough to read yesterday, then expire.
DAILY_TTL = 60 * 60 * 48

# Raise Redis to db_total only when missing or behind. Never lower a live counter.
_HEAL_USAGE_LUA = """
local db = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local cur = redis.call('GET', KEYS[1])
if not cur then
  redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ttl)
  return db
end
local n = tonumber(cur)
if n < db then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ttl)
  return db
end
return n
"""


# Floor the daily usage counter at 0 so a buggy double-refund can never drive it
# negative (which would grant the user free quota). Set on refund/record.
async def floor_counter(redis: Redis, key: str) -> None:
    """Clamp a counter to 0 without wiping its TTL (SET alone drops EXPIRE)."""
    await redis.set(key, 0, keepttl=True)


async def _reserve_daily_slot(redis: Redis, key: str, *, limit: int) -> bool:
    """Atomically take one slot from a per-day cap; roll back when over limit.

    INCR-then-rollback keeps parallel requests honest: the loser of a race
    lands over the limit and gives its slot back, so the cap can't be
    exceeded by concurrent calls. A limit of 0 (feature off / not entitled)
    always refuses.

    M10: Redis outages fail closed with ``RedisUnavailableError`` — same
    pattern as ``reserve_usage`` so speech/image/Tavily paths return 503
    instead of an opaque 500.
    """
    if limit <= 0:
        return False
    try:
        new_total = await redis.incrby(key, 1)
        if new_total == 1:
            await redis.expire(key, DAILY_TTL)
        if new_total > limit:
            await redis.incrby(key, -1)
            return False
        return True
    except RedisError as exc:
        logger.warning("Daily slot reserve failed; Redis unavailable key=%s", key, exc_info=True)
        raise RedisUnavailableError() from exc


async def refund_daily(redis: Redis, key: str, *, amount: int = 1) -> None:
    """Give back reserved units, flooring at zero (double-refund safe)."""
    new_total = await redis.incrby(key, -amount)
    if new_total < 0:
        await floor_counter(redis, key)


async def _refund_if_positive(redis: Redis, key: str) -> None:
    """Give back one unit only from a counter above zero; never create the key."""
    value = await redis.get(key)
    if not value:
        return
    if int(value) <= 0:
        return
    await redis.incrby(key, -1)


async def _raise_counter_cas(redis: Redis, key: str, floor: int, ttl: int) -> None:
    current = await redis.get(key)
    if current is None:
        await redis.set(key, floor, nx=True, ex=ttl)
        return
    if int(current) < floor:
        await redis.set(key, floor, ex=ttl)


async def raise_counter(redis: Redis, key: str, floor: int, *, ttl: int) -> None:
    """Raise a counter to *floor* when missing or behind; never lower it.

    Atomic via Lua; GET+SET fallback when EVAL is unavailable (some fakeredis
    setups).
    """
    try:
        await redis.eval(_HEAL_USAGE_LUA, 1, key, str(floor), str(ttl))
    except ResponseError:
        await _raise_counter_cas(redis, key, floor, ttl)


CounterName = Literal[
    "image_upload",
    "speech_transcription",
    "speech_tts",
    "tavily_search",
    "image_generation",
    "image_search",
]


@dataclass(frozen=True, kw_only=True)
class CounterSpec:
    """One daily cap: one slot per reserve under ``<prefix>:<user id>:<UTC day>``.

    ``allowance`` names the plan's cap (0 refuses without touching Redis).
    ``message`` is the (free, paid) copy for a refusal; None when a refusal is
    silent. ``refund`` is how a slot comes back: ``floor`` decrements and clamps
    a negative result to 0; ``if_positive`` decrements only a counter above 0,
    so a refund without its reserve never creates the key; None keeps the slot.
    """

    prefix: str
    allowance: Allowance
    message: tuple[str, str] | None
    refund: Literal["floor", "if_positive"] | None


# Account delete carries every prefix here to a new account for the same
# sign-in (``carryover.read_carried_usage``).
COUNTERS: dict[CounterName, CounterSpec] = {
    # Vision/image inputs cost more than text and aren't well captured by the
    # text token reserve, so image uploads are capped per user per UTC day.
    "image_upload": CounterSpec(
        prefix="imgup",
        allowance="daily_image_uploads",
        message=(IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE, IMAGE_LIMIT_EXCEEDED_MESSAGE_PAID),
        refund="if_positive",
    ),
    "speech_transcription": CounterSpec(
        prefix="speech",
        allowance="daily_speech_transcriptions",
        message=(SPEECH_LIMIT_EXCEEDED_MESSAGE, SPEECH_LIMIT_EXCEEDED_MESSAGE),
        refund="floor",
    ),
    "speech_tts": CounterSpec(
        prefix="tts",
        allowance="daily_speech_tts",
        message=(SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE, SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE),
        refund="floor",
    ),
    # Past the cap a turn searches DuckDuckGo instead; a reserved search stays spent.
    "tavily_search": CounterSpec(
        prefix="tavily",
        allowance="daily_web_searches",
        message=None,
        refund=None,
    ),
    "image_generation": CounterSpec(
        prefix="imggen",
        allowance="daily_image_generations",
        message=(
            IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE,
            IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PAID,
        ),
        refund="floor",
    ),
    # Reference-photo lookup: every plan, per-plan cap.
    "image_search": CounterSpec(
        prefix="imgsearch",
        allowance="daily_image_searches",
        message=(
            IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_FREE,
            IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_PAID,
        ),
        refund="floor",
    ),
}


def limit(counter: CounterName, user: User, settings: Settings) -> int:
    return allowance(user, COUNTERS[counter].allowance, settings)


async def reserve(counter: CounterName, redis: Redis, user: User, settings: Settings) -> bool:
    """Take one of today's *counter* slots for *user*; False at the plan's cap."""
    cap = limit(counter, user, settings)
    return await _reserve_daily_slot(redis, daily_key(COUNTERS[counter].prefix, user.id), limit=cap)


async def refund(counter: CounterName, redis: Redis, user_id: UUID) -> None:
    """Give back a reserved slot (a failed or cancelled request)."""
    spec = COUNTERS[counter]
    key = daily_key(spec.prefix, user_id)
    if spec.refund == "floor":
        await refund_daily(redis, key)
    elif spec.refund == "if_positive":
        await _refund_if_positive(redis, key)
    else:
        raise ValueError(f"{counter} slots are not refunded")


def limit_message(counter: CounterName, user: User) -> str:
    message = COUNTERS[counter].message
    if message is None:
        raise ValueError(f"{counter} refuses without a message")
    free, paid = message
    return plan_message(user, free=free, paid=paid)
