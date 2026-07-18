"""Shared stream finalization helpers for WS and SSE transports.

Product-level decisions (what ``done`` contains, how exceptions map to
error payloads) live here once; routers only handle transport plumbing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.exceptions import ChatServiceError, QuotaExceededError, RedisUnavailableError
from app.gateways.litellm_gateway import ModelUnavailableError

logger = logging.getLogger(__name__)

# How long to hold `done` waiting on the DB commit before falling back to a
# best-effort `done`. Long enough for a normal Neon round trip + usage write,
# short enough that a wedged finalize doesn't pin the socket forever. If the
# commit FAILS (vs. is slow) we send an error instead of a ghost `done`.
DONE_COMMIT_WAIT_SECONDS = 10.0

_DONE_PAYLOAD_KEYS = (
    "message_id",
    "recalled",
    "memory_hints",
    "context_summarized",
    "todos_sync",
    "search_sources",
    "final_content",
    "resolved_model",
    "fallback_used",
)


def pop_finalize_tasks(result: dict[str, Any]) -> asyncio.Task[None] | None:
    """Pop finalize tasks off the result dict; return the DB-commit task."""
    finalize_db_task = result.pop("_finalize_db_task", None)
    result.pop("_finalize_task", None)
    return finalize_db_task


async def await_finalize_commit(finalize_db_task: asyncio.Task[None] | None) -> bool:
    """Wait (bounded) for the turn's DB commit before sending ``done``.

    Returns True when the commit landed (or is still in-flight but slow, or
    there was no task to wait on) — in those cases ``done`` is sent best-effort
    and the finalize registry still guards the next turn. Returns False only
    when the finalize task actually FAILED, so the caller sends an error
    instead of a ghost ``done`` carrying a message_id for a row that never
    persisted.
    """
    if finalize_db_task is None:
        return True
    try:
        await asyncio.wait_for(finalize_db_task, DONE_COMMIT_WAIT_SECONDS)
        return True
    except TimeoutError:
        logger.warning(
            "Finalize commit still running after %ss; sending done best-effort",
            DONE_COMMIT_WAIT_SECONDS,
        )
        return True
    except Exception:
        logger.exception("Finalize commit failed before done")
        return False


def build_done_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Assemble the shared ``done`` event fields from a stream result dict."""
    done: dict[str, Any] = {"type": "done"}
    for key in _DONE_PAYLOAD_KEYS:
        value = result.get(key)
        if value:
            done[key] = value
    return done


def error_payload_for_exception(exc: BaseException) -> dict[str, Any]:
    """Map stream exceptions to the shared error event shape."""
    if isinstance(exc, QuotaExceededError):
        return {"type": "error", "code": "quota_exceeded", "message": exc.message}
    if isinstance(exc, RedisUnavailableError):
        return {"type": "error", "code": "unavailable", "message": exc.message}
    if isinstance(exc, ChatServiceError):
        return {"type": "error", "message": exc.message}
    if isinstance(exc, ModelUnavailableError):
        return {
            "type": "error",
            "code": exc.code,
            "message": exc.message,
            "failed_model": exc.failed_alias,
        }
    return {"type": "error", "message": "Something went wrong. Try again."}
