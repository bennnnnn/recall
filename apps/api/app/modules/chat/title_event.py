"""A new chat's title, handed to the phone that asked for it instead of polled for.

The ``topic`` job writes the title in the worker, a second or two after the first reply's
``done``. The phone used to read the chat every two seconds until it came (one or two
``GET /chats/{id}`` per new chat, 2026-11-08 feature test). Now the job also leaves the
title in Redis for a few minutes, and whoever waits on it reads it there: the turn's
socket sends it after ``done`` as a ``title`` event (``ws_turn``), and a phone with no
socket for the turn (SSE, a picture, live talk, a chat it left first) asks once with
``GET /chats/{id}?wait_for_title=true``, which waits here.

Best-effort throughout: a Redis error is logged and reads as no title yet, never an
error in the turn or the request.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from itertools import chain, repeat
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_KEY = "chat_title_ready:{chat_id}"
# Long enough for a phone that left the chat to come back and ask once.
_KEPT_SECONDS = 10 * 60
# The topic job takes a second or two; past this the phone stops waiting and reads the
# title with the chat list.
TITLE_WAIT_SECONDS = 8.0
# Looked for often while it is likely to land, then less: about four reads for a title that
# took 1.5 s, at most eight in the whole wait.
_POLL_STEPS = (0.3, 0.5, 0.7, 1.0, 1.5)
_POLL_LAST = 2.0


def _key(chat_id: UUID) -> str:
    return _KEY.format(chat_id=chat_id)


async def announce_title(redis: Redis, chat_id: UUID, title: str) -> None:
    """Leave the title the topic job just applied where a waiting turn or request reads it."""
    try:
        await redis.set(_key(chat_id), title, ex=_KEPT_SECONDS)
    except Exception:
        logger.warning("Chat title announce failed chat_id=%s", chat_id, exc_info=True)


async def _announced(redis: Redis, chat_id: UUID) -> str | None:
    try:
        title = await redis.get(_key(chat_id))
    except Exception:
        logger.warning("Chat title read failed chat_id=%s", chat_id, exc_info=True)
        return None
    return title if isinstance(title, str) and title.strip() else None


async def await_title(
    redis: Redis,
    chat_id: UUID,
    *,
    within: float | None = None,
    wanted: Callable[[], bool] = lambda: True,
) -> str | None:
    """The chat's new title once the topic job announces it, or None after ``within`` seconds
    (``TITLE_WAIT_SECONDS``), or once no one ``wanted`` it any more (the socket closed)."""
    deadline = time.monotonic() + (TITLE_WAIT_SECONDS if within is None else within)
    steps = chain(_POLL_STEPS, repeat(_POLL_LAST))
    while True:
        title = await _announced(redis, chat_id)
        if title is not None:
            return title
        left = deadline - time.monotonic()
        if left <= 0 or not wanted():
            return None
        await asyncio.sleep(min(next(steps), left))


def build_title_event(title: str | None) -> dict[str, Any]:
    """The chat's title, sent after ``done`` of the turn that asked for one (``title_pending``).

    ``title`` is None when the wait ran out: the phone stops waiting and reads it with the
    chat list.
    """
    return {"type": "title", "title": title}


async def title_event(
    redis: Redis, chat_id: UUID, wanted: Callable[[], bool] = lambda: True
) -> dict[str, Any]:
    return build_title_event(await await_title(redis, chat_id, wanted=wanted))
