"""Shared stream finalization helpers for WS and SSE transports.

Product-level decisions (what ``done`` contains, how exceptions map to
error payloads) live here once; routers only handle transport plumbing.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from app.exceptions import (
    ChatBusyError,
    ChatServiceError,
    QuotaExceededError,
    RedisUnavailableError,
)
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


def build_start_event() -> dict[str, Any]:
    """First frame of a turn; tells the client generation has begun."""
    return {"type": "start"}


def build_token_event(content: str) -> dict[str, Any]:
    """One chunk of assistant text."""
    return {"type": "token", "content": content}


def build_status_event(phase: str, detail: str | None = None) -> dict[str, Any]:
    """Turn-prep progress (see stream_status.StreamStatusPhase)."""
    event: dict[str, Any] = {"type": "status", "phase": phase}
    if detail:
        event["detail"] = detail
    return event


def build_reasoning_event(content: str) -> dict[str, Any]:
    """One chunk of reasoning-model thinking text."""
    return {"type": "reasoning", "content": content}


def build_stream_end_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Assemble the ``stream_end`` event fields from a stream result dict.

    Sent once the token stream is done but before the DB commit is awaited,
    so clients can settle layout while ``done`` is still pending.
    """
    stream_end: dict[str, Any] = {"type": "stream_end"}
    resolved_model = result.get("resolved_model")
    if resolved_model:
        stream_end["resolved_model"] = resolved_model
    if result.get("fallback_used"):
        stream_end["fallback_used"] = result["fallback_used"]
    return stream_end


def pop_finalize_tasks(result: dict[str, Any]) -> asyncio.Task[None] | None:
    """Pop finalize tasks off the result dict; return the DB-commit task."""
    finalize_db_task = result.pop("_finalize_db_task", None)
    result.pop("_finalize_task", None)
    return finalize_db_task


async def await_finalize_commit(
    finalize_db_task: asyncio.Task[None] | None,
) -> str:
    """Wait (bounded) for the turn's DB commit before sending ``done``.

    Returns:
      - ``"committed"`` when the commit landed (or there was no task).
      - ``"timeout"`` when the wait timed out while the commit is still
        running under ``asyncio.shield``. The caller should send ``done``
        WITHOUT ``message_id`` (and with ``persisting: true``) so the client
        keeps the local bubble and refetches instead of trusting a row that
        may never persist.
      - ``"failed"`` when the finalize task actually raised, so the caller
        sends an error instead of a ghost ``done`` carrying a ``message_id``
        for a row that never persisted.

    The wait must use ``shield``: bare ``wait_for`` cancels the finalize task
    on timeout, which rolls back the assistant insert and strands reserved
    quota while the client still receives ``done``.
    """
    if finalize_db_task is None:
        return "committed"
    try:
        await asyncio.wait_for(asyncio.shield(finalize_db_task), DONE_COMMIT_WAIT_SECONDS)
        return "committed"
    except TimeoutError:
        logger.warning(
            "Finalize commit still running after %ss; sending done without "
            "message_id (commit continues under shield)",
            DONE_COMMIT_WAIT_SECONDS,
        )
        return "timeout"
    except Exception:
        logger.exception("Finalize commit failed before done")
        return "failed"


async def persist_finalize_if_pending(result: dict[str, Any]) -> None:
    """Await a still-pending DB finalize after the transport drops.

    SSE and WS success paths pop and wait for ``done``. If the client closes
    first, that wait never runs — call this from a ``finally`` so a partial
    assistant row is still committed (quota refund + title job included).
    """
    finalize_db_task = pop_finalize_tasks(result)
    if finalize_db_task is None:
        return
    with suppress(Exception):
        await await_finalize_commit(finalize_db_task)


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
    if isinstance(exc, ChatBusyError):
        return {"type": "error", "code": "busy", "message": exc.message}
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
