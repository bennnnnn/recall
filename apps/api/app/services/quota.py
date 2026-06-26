from datetime import UTC, date, datetime

from redis.asyncio import Redis

from app.core.config import Settings


def _usage_key(user_id: str, day: date) -> str:
    return f"usage:{user_id}:{day.isoformat()}"


def utc_today() -> date:
    return datetime.now(UTC).date()


# Shown when the daily free quota is exhausted — avoid internal "token" wording.
QUOTA_EXCEEDED_MESSAGE = (
    "You've used up today's free limit. Go Pro for more — or come back tomorrow."
)


async def get_daily_usage(redis: Redis, user_id: str) -> int:
    key = _usage_key(user_id, utc_today())
    value = await redis.get(key)
    return int(value or 0)


async def can_spend(redis: Redis, user_id: str, requested: int, settings: Settings) -> bool:
    used = await get_daily_usage(redis, user_id)
    return used + requested <= settings.daily_token_limit


async def reserve_usage(redis: Redis, user_id: str, requested: int, settings: Settings) -> bool:
    """Atomically reserve tokens before generation. Refunds if over limit."""
    if requested <= 0:
        return True
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, requested)
    if new_total == requested:
        await redis.expire(key, 60 * 60 * 48)
    if new_total > settings.daily_token_limit:
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


async def remaining(redis: Redis, user_id: str, settings: Settings) -> int:
    used = await get_daily_usage(redis, user_id)
    return max(0, settings.daily_token_limit - used)
