"""The user's Stop for a reply streaming over SSE.

SSE is one-way, so a closed connection was its only Stop, and a dropped one (a tunnel,
the app sent to the background) stopped the reply as the user's Stop did: saved cut
short, with no checked cards and no Continue, where the socket finishes and saves it
(security review, 2026-11-25). The phone now names each SSE stream it opens
(``stream_id`` in the request) and says Stop for that stream on a request of its own
(``POST /chats/{id}/stream/stop``) before it closes it. Whatever machine runs the stream
reads that word once its client is gone; a stream gone with no Stop said finishes and
saves its reply, as the socket's does. A Stop names its stream, so one said late (the
reply was already saving) can never stop another turn, and the stream's key goes when its
reply is done.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.background_tasks import create_background_task
from app.exceptions import RedisUnavailableError

logger = logging.getLogger(__name__)

# A Stop is read within seconds of its stream closing; one never read goes on its own.
STOP_TTL_SECONDS = 30
# How long a stream whose client left waits for that client's Stop: the phone sends it
# before it closes the stream, on another connection that may land a little later.
STOP_GRACE_SECONDS = 3.0
_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class StopAsked:
    """A Stop the user said, with how much of the reply their client drew, when it said."""

    shown_chars: int | None


@dataclass(frozen=True)
class SseStop:
    """The Stop of one SSE stream: its user, its chat and the name its client gave it."""

    redis: Redis
    user_id: UUID
    chat_id: UUID
    stream_id: UUID

    @property
    def key(self) -> str:
        return f"sse_stop:{self.user_id}:{self.chat_id}:{self.stream_id}"

    async def ask(self, shown_chars: int | None) -> None:
        """Say Stop for this stream, wherever it runs. Redis down raises
        ``RedisUnavailableError`` (503): the phone's stream then closes as a drop, and the
        reply saves whole."""
        value = "" if shown_chars is None else str(shown_chars)
        try:
            await self.redis.set(self.key, value, ex=STOP_TTL_SECONDS)
        except (RedisError, OSError) as exc:
            raise RedisUnavailableError() from exc

    async def wait(self, *, grace: float = STOP_GRACE_SECONDS) -> StopAsked | None:
        """The Stop said for this stream, waiting up to ``grace`` for it to land; None when
        none came (the connection dropped) or Redis cannot say."""
        deadline = asyncio.get_running_loop().time() + grace
        while True:
            try:
                raw = await self.redis.getdel(self.key)
            except (RedisError, OSError):
                logger.warning("SSE Stop unreadable chat_id=%s", self.chat_id, exc_info=True)
                return None
            if raw is not None:
                text = raw.decode() if isinstance(raw, bytes) else str(raw)
                return StopAsked(int(text) if text.isdigit() else None)
            if asyncio.get_running_loop().time() >= deadline:
                return None
            await asyncio.sleep(_POLL_SECONDS)

    def clear_soon(self, _done: object = None) -> None:
        """Drop a Stop said for this stream after its reply is done (a done-callback)."""
        create_background_task(self._clear(), name="sse_stop_clear")

    async def _clear(self) -> None:
        try:
            await self.redis.delete(self.key)
        except (RedisError, OSError):
            logger.warning("SSE Stop not cleared chat_id=%s", self.chat_id, exc_info=True)
