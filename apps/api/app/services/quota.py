from datetime import UTC, date, datetime

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


def quota_exceeded_message(user: User) -> str:
    if user.plan == "pro":
        return QUOTA_EXCEEDED_MESSAGE_PRO
    return QUOTA_EXCEEDED_MESSAGE_FREE


def _usage_key(user_id: str, day: date) -> str:
    return f"usage:{user_id}:{day.isoformat()}"


def utc_today() -> date:
    return datetime.now(UTC).date()


def daily_limit_for_user(user: User, settings: Settings) -> int:
    if user.plan == "pro":
        return settings.daily_token_limit_pro
    return settings.daily_token_limit


async def get_daily_usage(redis: Redis, user_id: str) -> int:
    key = _usage_key(user_id, utc_today())
    value = await redis.get(key)
    return int(value or 0)


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
    await redis.incrby(_usage_key(user_id, utc_today()), -amount)


async def adjust_usage(redis: Redis, user_id: str, reserved: int, actual: int) -> int:
    delta = actual - reserved
    if delta == 0:
        return await get_daily_usage(redis, user_id)
    return await record_usage(redis, user_id, delta)


async def record_usage(redis: Redis, user_id: str, tokens: int) -> int:
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, tokens)
    if new_total == tokens:
        await redis.expire(key, 60 * 60 * 48)
    return new_total


async def remaining(redis: Redis, user_id: str, *, daily_limit: int) -> int:
    used = await get_daily_usage(redis, user_id)
    return max(0, daily_limit - used)


async def reset_daily_usage(redis: Redis, user_id: str, day: date | None = None) -> None:
    """Clear Redis quota counter for a user/day (dev support)."""
    await redis.delete(_usage_key(user_id, day or utc_today()))
