"""The day's chat messages: one slot per turn, from the plan's ``daily_messages``.

A turn takes its slot before the reply (``modules/chat/turn_resources``) and gives
it back on every path that saves no reply, as its token reservation does.
"""

from datetime import date
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.models.orm import User
from app.services.quota import counters


async def reserve_message(redis: Redis, user: User, settings: Settings) -> date | None:
    """Take one of today's messages; the UTC day charged, or None when none is left."""
    return await counters.reserve("chat_message", redis, user, settings)


async def refund_message(redis: Redis, user_id: UUID, day: date) -> None:
    """Give back the message a turn took on *day*: it saved no reply."""
    await counters.refund("chat_message", redis, user_id, day=day)


async def messages_used(redis: Redis, user_id: UUID) -> int:
    return await counters.used("chat_message", redis, user_id)


async def reset_messages(redis: Redis, user_id: UUID) -> None:
    """Today's messages back to none (the development reset)."""
    await redis.delete(counters.daily_key(counters.COUNTERS["chat_message"].prefix, user_id))


def daily_message_limit(user: User, settings: Settings) -> int:
    return counters.limit("chat_message", user, settings)
