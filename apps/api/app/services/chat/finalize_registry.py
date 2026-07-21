"""Per-chat registry of in-flight turn finalization tasks.

The chat routers send `done` to the client as soon as the token stream ends,
while the DB commit (assistant message insert, usage, quota) finishes in a
background task. Anything that reads a chat's messages right after a turn —
the next turn's prompt build, regenerate/edit, message feedback — must await
that pending commit first or it can miss the just-streamed assistant reply.

Same-process waiters use an in-memory task map. Cross-process / multi-instance
waiters also poll a short-lived Redis marker set when finalize is registered
and cleared when the DB task finishes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_FINALIZE_WAIT_TIMEOUT_SECONDS = 10.0
_FINALIZE_MARKER_TTL_SECONDS = 120
_FINALIZE_POLL_INTERVAL_SECONDS = 0.05

_pending: dict[UUID, asyncio.Task[None]] = {}


def _marker_key(chat_id: UUID) -> str:
    return f"chatfinal:{chat_id}"


def register_pending_finalize(chat_id: UUID, task: asyncio.Task[None]) -> None:
    """Track `task` as the chat's in-flight finalize; auto-clears on completion."""
    _pending[chat_id] = task

    def _clear(done: asyncio.Task[None]) -> None:
        if _pending.get(chat_id) is done:
            _pending.pop(chat_id, None)

    task.add_done_callback(_clear)


async def mark_pending_finalize(redis: Redis, chat_id: UUID) -> None:
    """Publish a cross-process "finalize in flight" marker for ``chat_id``."""
    try:
        await redis.set(_marker_key(chat_id), "1", ex=_FINALIZE_MARKER_TTL_SECONDS)
    except Exception:
        logger.debug("Failed to mark pending finalize chat_id=%s", chat_id, exc_info=True)


async def clear_pending_finalize(redis: Redis, chat_id: UUID) -> None:
    """Clear the cross-process finalize marker after commit attempt finishes."""
    try:
        await redis.delete(_marker_key(chat_id))
    except Exception:
        logger.debug("Failed to clear pending finalize chat_id=%s", chat_id, exc_info=True)


async def wait_for_pending_finalize(chat_id: UUID, redis: Redis | None = None) -> None:
    """Wait (bounded) for the chat's previous turn to finish committing.

    Never raises: a failed or slow finalize must not block the next turn —
    the finalize task logs its own errors.
    """
    task = _pending.get(chat_id)
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), _FINALIZE_WAIT_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("Pending turn finalize still running after wait chat_id=%s", chat_id)
        except Exception:
            # The finalize task's own error handling/logging covers this.
            with contextlib.suppress(Exception):
                logger.debug("Pending finalize failed chat_id=%s", chat_id, exc_info=True)
        return

    if redis is None:
        return

    # Another API machine may own the finalize task — poll the Redis marker.
    deadline = time.monotonic() + _FINALIZE_WAIT_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline:
            if not await redis.exists(_marker_key(chat_id)):
                return
            await asyncio.sleep(_FINALIZE_POLL_INTERVAL_SECONDS)
        logger.warning("Pending turn finalize marker still set after wait chat_id=%s", chat_id)
    except Exception:
        logger.debug("Pending finalize Redis wait failed chat_id=%s", chat_id, exc_info=True)


def pending_finalize_count() -> int:
    """Test/introspection helper."""
    return len(_pending)
