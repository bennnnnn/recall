"""The day's chat messages: one slot per turn, from the plan's ``daily_messages``.

A turn takes its slot before the reply (``modules/chat/turn_resources``) and gives
it back on every path that saves no reply, as its token reservation does.
"""

from datetime import date
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.services.quota.counters import (
    COUNTERS,
    daily_key,
    limit,
    refund,
    reserve,
    unlimited,
    used,
)


async def reserve_message(redis: Redis, user: User, settings: Settings) -> date | None:
    """Take one of today's messages; the UTC day charged, or None when none is left."""
    return await reserve("chat_message", redis, user, settings)


async def refund_message(redis: Redis, user_id: UUID, day: date) -> None:
    """Give back the message a turn took on *day*: it saved no reply."""
    await refund("chat_message", redis, user_id, day=day)


async def messages_used(redis: Redis, user_id: UUID) -> int:
    return await used("chat_message", redis, user_id)


async def reset_messages(redis: Redis, user_id: UUID) -> None:
    """Today's messages back to none (the development reset)."""
    await redis.delete(daily_key(COUNTERS["chat_message"].prefix, user_id))


async def has_message_left(redis: Redis, user: User, settings: Settings) -> bool:
    """Whether *user* may still send a message today (an upload waits for its send)."""
    if unlimited_messages(user, settings):
        return True
    try:
        used_today = await messages_used(redis, user.id)
    except RedisError as exc:
        raise RedisUnavailableError() from exc
    return used_today < daily_message_limit(user, settings)


def unlimited_messages(user: User, settings: Settings) -> bool:
    """The plan has no daily message cap (Pro): its token guard is the only daily stop."""
    return unlimited("chat_message", user, settings)


def daily_message_limit(user: User, settings: Settings) -> int:
    """The plan's messages a day; 0 on an unlimited plan, which shows no count."""
    return limit("chat_message", user, settings)
