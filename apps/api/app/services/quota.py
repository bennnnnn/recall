import logging
from datetime import UTC, date, datetime
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User

logger = logging.getLogger(__name__)

# Shown when the daily quota is exhausted — avoid internal "token" wording.
QUOTA_EXCEEDED_MESSAGE_FREE = (
    "You've used up today's free limit. Go Pro for more — or come back tomorrow."
)
QUOTA_EXCEEDED_MESSAGE_PRO = "You've reached today's limit. Come back tomorrow."

# Backward-compatible alias for tests and imports.
QUOTA_EXCEEDED_MESSAGE = QUOTA_EXCEEDED_MESSAGE_FREE

IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "You've reached today's image upload limit (5). Go Pro for more — or come back tomorrow."
)
IMAGE_LIMIT_EXCEEDED_MESSAGE_PRO = (
    "You've reached today's image upload limit (30). Come back tomorrow."
)

SPEECH_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "You've reached today's voice transcription limit. Go Pro for more — or come back tomorrow."
)
SPEECH_LIMIT_EXCEEDED_MESSAGE_PRO = (
    "You've reached today's voice transcription limit. Come back tomorrow."
)
SPEECH_RATE_LIMIT_MESSAGE = "Too many voice requests. Please wait a moment and try again."
SPEECH_TTS_RATE_LIMIT_MESSAGE = "Too many read-aloud requests. Please wait a moment and try again."

IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "Image generation is a Pro feature. Upgrade to generate images."
)
IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PRO = (
    "You've reached today's image generation limit. Come back tomorrow."
)


def _plan_limit(user: User, *, free: int, pro: int) -> int:
    return pro if user.plan == "pro" else free


def _plan_message(user: User, *, free: str, pro: str) -> str:
    return pro if user.plan == "pro" else free


def quota_exceeded_message(user: User) -> str:
    return _plan_message(user, free=QUOTA_EXCEEDED_MESSAGE_FREE, pro=QUOTA_EXCEEDED_MESSAGE_PRO)


def image_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free=IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE,
        pro=IMAGE_LIMIT_EXCEEDED_MESSAGE_PRO,
    )


def speech_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free=SPEECH_LIMIT_EXCEEDED_MESSAGE_FREE,
        pro=SPEECH_LIMIT_EXCEEDED_MESSAGE_PRO,
    )


def image_generation_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free=IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE,
        pro=IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PRO,
    )


def speech_tts_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free="Daily read-aloud limit reached. Upgrade to Pro for more, or use device speech.",
        pro="Daily read-aloud limit reached. Try again tomorrow.",
    )


def utc_today() -> date:
    return datetime.now(UTC).date()


def _daily_key(prefix: str, owner: str | UUID, day: date | None = None) -> str:
    """Per-user, per-UTC-day counter key shared by every daily cap."""
    return f"{prefix}:{owner}:{(day or utc_today()).isoformat()}"


def _usage_key(user_id: str, day: date) -> str:
    return _daily_key("usage", user_id, day)


# Daily counters outlive their day by enough to read yesterday, then expire.
_DAILY_TTL = 60 * 60 * 48


# Floor the daily usage counter at 0 so a buggy double-refund can never drive it
# negative (which would grant the user free quota). Set on refund/record.
async def _floor_counter(redis: Redis, key: str) -> None:
    """Clamp a counter to 0 without wiping its TTL (SET alone drops EXPIRE)."""
    await redis.set(key, 0, keepttl=True)


async def _reserve_daily_slot(redis: Redis, key: str, *, limit: int) -> bool:
    """Atomically take one slot from a per-day cap; roll back when over limit.

    INCR-then-rollback keeps parallel requests honest: the loser of a race
    lands over the limit and gives its slot back, so the cap can't be
    exceeded by concurrent calls. A limit of 0 (feature off / not entitled)
    always refuses.
    """
    if limit <= 0:
        return False
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _DAILY_TTL)
    if new_total > limit:
        await redis.incrby(key, -1)
        return False
    return True


async def _refund_daily(redis: Redis, key: str, *, amount: int = 1) -> None:
    """Give back reserved units, flooring at zero (double-refund safe)."""
    new_total = await redis.incrby(key, -amount)
    if new_total < 0:
        await _floor_counter(redis, key)


def daily_limit_for_user(user: User, settings: Settings) -> int:
    return _plan_limit(user, free=settings.daily_token_limit, pro=settings.daily_token_limit_pro)


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
    await redis.set(key, db_total, nx=True, ex=_DAILY_TTL)


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
            await redis.expire(key, _DAILY_TTL)
        if new_total > daily_limit:
            await redis.incrby(key, -requested)
            return False
        return True
    except RedisError as exc:
        logger.warning("Quota reserve failed; Redis unavailable user_id=%s", user_id, exc_info=True)
        raise RedisUnavailableError() from exc


async def refund_usage(redis: Redis, user_id: str, amount: int) -> None:
    if amount <= 0:
        return
    await _refund_daily(redis, _usage_key(user_id, utc_today()), amount=amount)


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
        await redis.expire(key, _DAILY_TTL)
    if new_total < 0:
        await _floor_counter(redis, key)
        new_total = 0
    # Cap overshoot: a single turn whose actual usage exceeds the reserve
    # estimate can push the daily counter past the limit. Clip at daily_limit
    # so one turn can't blow the cap (the over-limit tokens are forfeit —
    # they were genuinely used, but the counter must not exceed the limit
    # or subsequent reserve_usage checks under-report remaining quota).
    if daily_limit is not None and new_total > daily_limit:
        await redis.set(key, daily_limit, ex=_DAILY_TTL)
        new_total = daily_limit
    return new_total


async def remaining(redis: Redis, user_id: str, *, daily_limit: int) -> int:
    used = await get_daily_usage(redis, user_id)
    return max(0, daily_limit - used)


async def reset_daily_usage(redis: Redis, user_id: str, day: date | None = None) -> None:
    """Clear Redis quota counter for a user/day (dev support)."""
    await redis.delete(_usage_key(user_id, day or utc_today()))


# ── Daily image-upload cap (separate from the token quota) ───────────────────
# Vision/image inputs cost more than text and aren't well captured by the text
# token reserve, so image uploads are capped per user per UTC day. Counted at
# upload-completion time (when bytes are actually stored); checked at presign.


def image_upload_limit_for_user(user: User, settings: Settings) -> int:
    return _plan_limit(user, free=settings.daily_image_limit, pro=settings.daily_image_limit_pro)


async def get_image_upload_count(redis: Redis, user_id: UUID) -> int:
    value = await redis.get(_daily_key("imgup", user_id))
    return int(value or 0)


async def record_image_upload(redis: Redis, user_id: UUID) -> int:
    key = _daily_key("imgup", user_id)
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _DAILY_TTL)
    return new_total


async def reserve_image_upload(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    """Atomically reserve one image upload slot for today. Rolls back if over limit."""
    return await _reserve_daily_slot(redis, _daily_key("imgup", user_id), limit=limit)


async def refund_image_upload(redis: Redis, user_id: UUID) -> None:
    """Release a reserved image slot (e.g. failed or cancelled upload). Floors at zero.

    Unlike the other refunds this never decrements below an absent/zero key —
    a refund without a matching reserve must not create a negative counter.
    """
    key = _daily_key("imgup", user_id)
    value = await redis.get(key)
    if not value:
        return
    if int(value) <= 0:
        return
    await redis.incrby(key, -1)


# ── Speech transcription caps ────────────────────────────────────────────────


def speech_transcription_limit_for_user(user: User, settings: Settings) -> int:
    return _plan_limit(
        user,
        free=settings.daily_speech_transcriptions,
        pro=settings.daily_speech_transcriptions_pro,
    )


async def reserve_speech_transcription(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("speech", user_id), limit=limit)


async def refund_speech_transcription(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("speech", user_id))


def speech_tts_limit_for_user(user: User, settings: Settings) -> int:
    return _plan_limit(user, free=settings.daily_speech_tts, pro=settings.daily_speech_tts_pro)


async def reserve_speech_tts(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("tts", user_id), limit=limit)


async def refund_speech_tts(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("tts", user_id))


# ── Tavily web-search caps (DDG fallback when exceeded) ────────────────────────


def tavily_search_limit_for_user(user: User, settings: Settings) -> int:
    return _plan_limit(
        user,
        free=settings.daily_tavily_searches,
        pro=settings.daily_tavily_searches_pro,
    )


async def reserve_tavily_search(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("tavily", user_id), limit=limit)


# ── AI image generation caps (Pro-only via limit=0 for free) ─────────────────


def image_generation_limit_for_user(user: User, settings: Settings) -> int:
    return _plan_limit(
        user,
        free=settings.daily_image_generations,
        pro=settings.daily_image_generations_pro,
    )


async def reserve_image_generation(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("imggen", user_id), limit=limit)


async def refund_image_generation(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("imggen", user_id))
