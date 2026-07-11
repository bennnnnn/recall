"""Per-chat registry of in-flight turn finalization tasks.

The chat routers send `done` to the client as soon as the token stream ends,
while the DB commit (assistant message insert, usage, quota) finishes in a
background task. Anything that reads a chat's messages right after a turn —
the next turn's prompt build, regenerate/edit, message feedback — must await
that pending commit first or it can miss the just-streamed assistant reply.

In-memory and per-process: consecutive turns from one client arrive over the
same WebSocket (or the same API instance), which is where the race lives.
"""

import asyncio
import contextlib
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

_FINALIZE_WAIT_TIMEOUT_SECONDS = 10.0

_pending: dict[UUID, asyncio.Task[None]] = {}


def register_pending_finalize(chat_id: UUID, task: asyncio.Task[None]) -> None:
    """Track `task` as the chat's in-flight finalize; auto-clears on completion."""
    _pending[chat_id] = task

    def _clear(done: asyncio.Task[None]) -> None:
        if _pending.get(chat_id) is done:
            _pending.pop(chat_id, None)

    task.add_done_callback(_clear)


async def wait_for_pending_finalize(chat_id: UUID) -> None:
    """Wait (bounded) for the chat's previous turn to finish committing.

    Never raises: a failed or slow finalize must not block the next turn —
    the finalize task logs its own errors.
    """
    task = _pending.get(chat_id)
    if task is None or task.done():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), _FINALIZE_WAIT_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("Pending turn finalize still running after wait chat_id=%s", chat_id)
    except Exception:
        # The finalize task's own error handling/logging covers this.
        with contextlib.suppress(Exception):
            logger.debug("Pending finalize failed chat_id=%s", chat_id, exc_info=True)


def pending_finalize_count() -> int:
    """Test/introspection helper."""
    return len(_pending)
