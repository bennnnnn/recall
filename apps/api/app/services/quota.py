from datetime import UTC, date, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.models.orm import User

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
SPEECH_RATE_LIMIT_MESSAGE = "Too many transcription requests. Please wait a moment and try again."

IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "Image generation is a Pro feature. Upgrade to generate images."
)
IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PRO = (
    "You've reached today's image generation limit. Come back tomorrow."
)


def quota_exceeded_message(user: User) -> str:
    if user.plan == "pro":
        return QUOTA_EXCEEDED_MESSAGE_PRO
    return QUOTA_EXCEEDED_MESSAGE_FREE


def image_limit_exceeded_message(user: User) -> str:
    if user.plan == "pro":
        return IMAGE_LIMIT_EXCEEDED_MESSAGE_PRO
    return IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE


def speech_limit_exceeded_message(user: User) -> str:
    if user.plan == "pro":
        return SPEECH_LIMIT_EXCEEDED_MESSAGE_PRO
    return SPEECH_LIMIT_EXCEEDED_MESSAGE_FREE


def image_generation_limit_exceeded_message(user: User) -> str:
    if user.plan == "pro":
        return IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PRO
    return IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE


def _usage_key(user_id: str, day: date) -> str:
    return f"usage:{user_id}:{day.isoformat()}"


def utc_today() -> date:
    return datetime.now(UTC).date()


# Floor the daily usage counter at 0 so a buggy double-refund can never drive it
# negative (which would grant the user free quota). Set on refund/record.
_USAGE_TTL = 60 * 60 * 48


def daily_limit_for_user(user: User, settings: Settings) -> int:
    if user.plan == "pro":
        return settings.daily_token_limit_pro
    return settings.daily_token_limit


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
    await redis.set(key, db_total, nx=True, ex=_USAGE_TTL)


async def can_spend(
    redis: Redis,
    user_id: str,
    requested: int,
    *,
    daily_limit: int,
) -> bool:
    used = await get_daily_usage(redis, user_id)
    return used + requested <= daily_limit


async def reserve_usage(
    redis: Redis,
    user_id: str,
    requested: int,
    *,
    daily_limit: int,
) -> bool:
    """Atomically reserve tokens before generation. Refunds if over limit."""
    if requested <= 0:
        return True
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, requested)
    if new_total == requested:
        await redis.expire(key, 60 * 60 * 48)
    if new_total > daily_limit:
        await redis.incrby(key, -requested)
        return False
    return True


async def refund_usage(redis: Redis, user_id: str, amount: int) -> None:
    if amount <= 0:
        return
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, -amount)
    if new_total < 0:
        await redis.set(key, 0)


async def adjust_usage(redis: Redis, user_id: str, reserved: int, actual: int) -> int:
    delta = actual - reserved
    if delta == 0:
        return await get_daily_usage(redis, user_id)
    return await record_usage(redis, user_id, delta)


async def record_usage(redis: Redis, user_id: str, tokens: int) -> int:
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, tokens)
    if new_total == tokens:
        await redis.expire(key, _USAGE_TTL)
    if new_total < 0:
        await redis.set(key, 0)
        new_total = 0
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

_IMAGE_TTL = 60 * 60 * 48


def _image_key(user_id: UUID, day: date) -> str:
    return f"imgup:{user_id}:{day.isoformat()}"


def image_upload_limit_for_user(user: User, settings: Settings) -> int:
    return settings.daily_image_limit_pro if user.plan == "pro" else settings.daily_image_limit


async def get_image_upload_count(redis: Redis, user_id: UUID) -> int:
    value = await redis.get(_image_key(user_id, utc_today()))
    return int(value or 0)


async def record_image_upload(redis: Redis, user_id: UUID) -> int:
    key = _image_key(user_id, utc_today())
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _IMAGE_TTL)
    return new_total


async def reserve_image_upload(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    """Atomically reserve one image upload slot for today. Rolls back if over limit."""
    if limit <= 0:
        return False
    key = _image_key(user_id, utc_today())
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _IMAGE_TTL)
    if new_total > limit:
        await redis.incrby(key, -1)
        return False
    return True


async def refund_image_upload(redis: Redis, user_id: UUID) -> None:
    """Release a reserved image slot (e.g. failed or cancelled upload). Floors at zero."""
    key = _image_key(user_id, utc_today())
    value = await redis.get(key)
    if not value:
        return
    if int(value) <= 0:
        return
    await redis.incrby(key, -1)


# ── Speech transcription caps ────────────────────────────────────────────────

_SPEECH_TTL = 60 * 60 * 48


def _speech_key(user_id: UUID, day: date) -> str:
    return f"speech:{user_id}:{day.isoformat()}"


def speech_transcription_limit_for_user(user: User, settings: Settings) -> int:
    if user.plan == "pro":
        return settings.daily_speech_transcriptions_pro
    return settings.daily_speech_transcriptions


async def reserve_speech_transcription(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    if limit <= 0:
        return False
    key = _speech_key(user_id, utc_today())
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _SPEECH_TTL)
    if new_total > limit:
        await redis.incrby(key, -1)
        return False
    return True


async def refund_speech_transcription(redis: Redis, user_id: UUID) -> None:
    key = _speech_key(user_id, utc_today())
    new_total = await redis.incrby(key, -1)
    if new_total < 0:
        await redis.set(key, 0)


# ── Tavily web-search caps (DDG fallback when exceeded) ────────────────────────

_TAVILY_TTL = 60 * 60 * 48


def _tavily_key(user_id: UUID, day: date) -> str:
    return f"tavily:{user_id}:{day.isoformat()}"


def tavily_search_limit_for_user(user: User, settings: Settings) -> int:
    if user.plan == "pro":
        return settings.daily_tavily_searches_pro
    return settings.daily_tavily_searches


async def reserve_tavily_search(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    if limit <= 0:
        return False
    key = _tavily_key(user_id, utc_today())
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _TAVILY_TTL)
    if new_total > limit:
        await redis.incrby(key, -1)
        return False
    return True


# ── AI image generation caps (Pro-only via limit=0 for free) ─────────────────

_IMGGEN_TTL = 60 * 60 * 48


def _imggen_key(user_id: UUID, day: date) -> str:
    return f"imggen:{user_id}:{day.isoformat()}"


def image_generation_limit_for_user(user: User, settings: Settings) -> int:
    if user.plan == "pro":
        return settings.daily_image_generations_pro
    return settings.daily_image_generations


async def reserve_image_generation(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    if limit <= 0:
        return False
    key = _imggen_key(user_id, utc_today())
    new_total = await redis.incrby(key, 1)
    if new_total == 1:
        await redis.expire(key, _IMGGEN_TTL)
    if new_total > limit:
        await redis.incrby(key, -1)
        return False
    return True


async def refund_image_generation(redis: Redis, user_id: UUID) -> None:
    key = _imggen_key(user_id, utc_today())
    new_total = await redis.incrby(key, -1)
    if new_total < 0:
        await redis.set(key, 0)
