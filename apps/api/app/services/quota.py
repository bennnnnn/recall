from datetime import UTC, date, datetime

from redis.asyncio import Redis

from app.core.config import Settings


def _usage_key(user_id: str, day: date) -> str:
    return f"usage:{user_id}:{day.isoformat()}"


async def get_daily_usage(redis: Redis, user_id: str) -> int:
    key = _usage_key(user_id, datetime.now(UTC).date())
    value = await redis.get(key)
    return int(value or 0)


async def can_spend(redis: Redis, user_id: str, requested: int, settings: Settings) -> bool:
    used = await get_daily_usage(redis, user_id)
    return used + requested <= settings.daily_token_limit


async def record_usage(redis: Redis, user_id: str, tokens: int) -> int:
    key = _usage_key(user_id, datetime.now(UTC).date())
    new_total = await redis.incrby(key, tokens)
    if new_total == tokens:
        await redis.expire(key, 60 * 60 * 48)
    return new_total


async def remaining(redis: Redis, user_id: str, settings: Settings) -> int:
    used = await get_daily_usage(redis, user_id)
    return max(0, settings.daily_token_limit - used)
