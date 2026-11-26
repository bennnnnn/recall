"""The user's Stop for a reply streaming over SSE.

SSE is one-way, so a closed connection was its only Stop, and a dropped one (a tunnel,
the app sent to the background) stopped the reply as the user's Stop did: saved cut
short, with no checked cards and no Continue, where the socket finishes and saves it
(security review, 2026-11-25). The phone now says Stop on a request of its own
(``POST /chats/{id}/stream/stop``) before it closes the stream. Whatever machine runs the
stream reads that word once its client is gone; a stream gone with no Stop said finishes
and saves its reply, as the socket's does.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.exceptions import RedisUnavailableError

logger = logging.getLogger(__name__)

# A Stop is read within seconds of its stream closing; one never read goes on its own.
STOP_TTL_SECONDS = 30
# How long a stream whose client left waits for that client's Stop: the phone sends it
# just before it closes the stream, on another connection that may land a little later.
STOP_GRACE_SECONDS = 3.0
_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class StopAsked:
    """A Stop the user said, with how much of the reply their client drew, when it said."""

    shown_chars: int | None


def _key(user_id: UUID, chat_id: UUID) -> str:
    return f"sse_stop:{user_id}:{chat_id}"


async def ask_stop(redis: Redis, user_id: UUID, chat_id: UUID, shown_chars: int | None) -> None:
    """Say Stop for the reply streaming in the user's chat, wherever its stream runs.
    Redis down raises ``RedisUnavailableError`` (503): the phone's stream then closes as a
    drop, and the reply saves whole."""
    value = "" if shown_chars is None else str(shown_chars)
    try:
        await redis.set(_key(user_id, chat_id), value, ex=STOP_TTL_SECONDS)
    except (RedisError, OSError) as exc:
        raise RedisUnavailableError() from exc


async def _take_stop(redis: Redis, user_id: UUID, chat_id: UUID) -> StopAsked | None:
    raw = await redis.getdel(_key(user_id, chat_id))
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    return StopAsked(int(text) if text.isdigit() else None)


async def wait_for_stop(
    redis: Redis, user_id: UUID, chat_id: UUID, *, grace: float = STOP_GRACE_SECONDS
) -> StopAsked | None:
    """The Stop the user said for this chat's stream, waiting up to ``grace`` for it to
    land; None when none came (the connection dropped) or Redis cannot say."""
    deadline = asyncio.get_running_loop().time() + grace
    while True:
        try:
            asked = await _take_stop(redis, user_id, chat_id)
        except (RedisError, OSError):
            logger.warning("SSE Stop unreadable chat_id=%s", chat_id, exc_info=True)
            return None
        if asked is not None or asyncio.get_running_loop().time() >= deadline:
            return asked
        await asyncio.sleep(_POLL_SECONDS)
