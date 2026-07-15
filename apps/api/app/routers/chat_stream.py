"""HTTP SSE fallback for chat streaming (WebSocket alternative for web/proxy clients)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.core.redis import get_redis_client
from app.exceptions import ChatServiceError, QuotaExceededError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.orm import User
from app.models.schemas import ChatMessageRequest, EditMessageRequest
from app.services import chat as chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chat-stream"])

_DISCONNECT_POLL_SECONDS = 0.5
# How long to hold `done` waiting on the DB commit before falling back to a
# best-effort `done`. Matches the WS path; see _await_finalize_commit.
_DONE_COMMIT_WAIT_SECONDS = 10.0


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _pop_finalize_tasks(result: dict[str, Any]) -> asyncio.Task[None] | None:
    """Pop the finalize tasks off the result dict, returning the DB-commit task
    so it can be awaited before `done` is emitted (the message_id must reference
    a committed row, not a pre-assigned id that might never land)."""
    finalize_db_task = result.pop("_finalize_db_task", None)
    result.pop("_finalize_task", None)
    return finalize_db_task


async def _await_finalize_commit(finalize_db_task: asyncio.Task[None] | None) -> bool:
    """Bounded wait for the turn's DB commit before `done`.

    Returns True when the commit landed (or is still in-flight but slow, or
    there was no task) — `done` is sent best-effort and the finalize registry
    still guards the next turn. Returns False only when the finalize task
    actually FAILED, so the caller emits an error instead of a ghost `done`.
    """
    if finalize_db_task is None:
        return True
    try:
        await asyncio.wait_for(finalize_db_task, _DONE_COMMIT_WAIT_SECONDS)
        return True
    except TimeoutError:
        logger.warning(
            "Finalize commit still running after %ss; sending done best-effort",
            _DONE_COMMIT_WAIT_SECONDS,
        )
        return True
    except Exception:
        logger.exception("Finalize commit failed before done")
        return False


async def _stream_tokens_sse(
    *,
    chat_id: UUID,
    settings: Settings,
    stream_factory: Callable[
        [dict[str, Any], Callable[[str], Any], Callable[[str], Any]],
        AsyncIterator[str],
    ],
    request: Request,
    cancel_event: asyncio.Event,
) -> AsyncIterator[str]:
    result: dict[str, Any] = {}
    event_queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()
    yield _sse({"type": "start"})

    async def on_status(phase: str) -> None:
        await event_queue.put(("status", phase))

    async def on_reasoning(chunk: str) -> None:
        await event_queue.put(("reasoning", chunk))

    def should_cancel() -> bool:
        return cancel_event.is_set()

    async def produce_tokens() -> None:
        try:
            stream = stream_factory(result, on_status, on_reasoning)
            async for token_text in stream:
                if should_cancel():
                    break
                await event_queue.put(("token", token_text))
        finally:
            await event_queue.put(None)

    async def watch_disconnect() -> None:
        """SSE is one-way, so a client's only way to stop generation is
        closing the connection — without this, a closed tab left the LLM
        call running to completion with tokens streamed to nobody, still
        burning quota and provider cost. `cancel_event` is also passed as
        `should_cancel` into the actual chat_service stream call, so setting
        it here stops generation at the source, not just this relay."""
        try:
            while not cancel_event.is_set():
                if await request.is_disconnected():
                    cancel_event.set()
                    await event_queue.put(None)
                    return
                await asyncio.sleep(_DISCONNECT_POLL_SECONDS)
        except asyncio.CancelledError:
            pass

    producer = asyncio.create_task(produce_tokens())
    disconnect_watcher = asyncio.create_task(watch_disconnect())

    try:
        while True:
            item = await event_queue.get()
            if item is None:
                break
            kind, payload = item
            if kind == "status":
                yield _sse({"type": "status", "phase": payload})
            elif kind == "reasoning":
                yield _sse({"type": "reasoning", "content": payload})
            else:
                yield _sse({"type": "token", "content": payload})

        await producer
        if (exc := producer.exception()) is not None:
            raise exc

        stream_end: dict[str, Any] = {"type": "stream_end"}
        resolved_model = result.get("resolved_model")
        if resolved_model:
            stream_end["resolved_model"] = resolved_model
        if result.get("fallback_used"):
            stream_end["fallback_used"] = result["fallback_used"]
        yield _sse(stream_end)
        finalize_db_task = _pop_finalize_tasks(result)
        if not await _await_finalize_commit(finalize_db_task):
            yield _sse({"type": "error", "message": "Failed to save the response. Please retry."})
            return

        done: dict[str, Any] = {"type": "done"}
        for key in (
            "message_id",
            "recalled",
            "memory_hints",
            "context_summarized",
            "todos_sync",
            "search_sources",
            "final_content",
            "resolved_model",
            "fallback_used",
        ):
            value = result.get(key)
            if value:
                done[key] = value
        yield _sse(done)
    except QuotaExceededError as exc:
        yield _sse({"type": "error", "code": "quota_exceeded", "message": exc.message})
    except ChatServiceError as exc:
        yield _sse({"type": "error", "message": exc.message})
    except ModelUnavailableError as exc:
        yield _sse(
            {
                "type": "error",
                "code": exc.code,
                "message": exc.message,
                "failed_model": exc.failed_alias,
            }
        )
    except Exception:
        logger.exception("SSE chat stream failed chat_id=%s", chat_id)
        yield _sse({"type": "error", "message": "Something went wrong. Try again."})
    finally:
        cancel_event.set()
        if not producer.done():
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer
        if not disconnect_watcher.done():
            disconnect_watcher.cancel()
            with suppress(asyncio.CancelledError):
                await disconnect_watcher


def _sse_response(body: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{chat_id}/messages/stream")
async def stream_message_sse(
    chat_id: UUID,
    body: ChatMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    redis = get_redis_client()
    cancel_event = asyncio.Event()

    async def generate() -> AsyncIterator[str]:
        async for chunk in _stream_tokens_sse(
            chat_id=chat_id,
            settings=settings,
            request=request,
            cancel_event=cancel_event,
            stream_factory=lambda result,
            on_status,
            on_reasoning: chat_service.stream_chat_response(
                redis,
                settings,
                user_id=user.id,
                chat_id=chat_id,
                content=body.content,
                model_alias=body.model,
                attachment_ids=body.attachment_ids or None,
                should_cancel=cancel_event.is_set,
                result=result,
                client_timezone=body.client_timezone,
                client_location=body.client_location,
                client_latitude=body.client_latitude,
                client_longitude=body.client_longitude,
                on_status=on_status,
                on_reasoning=on_reasoning,
                user=user,
            ),
        ):
            yield chunk

    return _sse_response(generate())


@router.post("/{chat_id}/regenerate/stream")
async def stream_regenerate_sse(
    chat_id: UUID,
    body: ChatMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    redis = get_redis_client()
    cancel_event = asyncio.Event()

    async def generate() -> AsyncIterator[str]:
        async for chunk in _stream_tokens_sse(
            chat_id=chat_id,
            settings=settings,
            request=request,
            cancel_event=cancel_event,
            stream_factory=lambda result,
            on_status,
            on_reasoning: chat_service.stream_regenerate_response(
                redis,
                settings,
                user_id=user.id,
                chat_id=chat_id,
                model_alias=body.model,
                should_cancel=cancel_event.is_set,
                result=result,
                client_timezone=body.client_timezone,
                client_location=body.client_location,
                client_latitude=body.client_latitude,
                client_longitude=body.client_longitude,
                on_status=on_status,
                on_reasoning=on_reasoning,
            ),
        ):
            yield chunk

    return _sse_response(generate())


@router.post("/{chat_id}/edit/stream")
async def stream_edit_sse(
    chat_id: UUID,
    body: EditMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    redis = get_redis_client()
    cancel_event = asyncio.Event()

    async def generate() -> AsyncIterator[str]:
        async for chunk in _stream_tokens_sse(
            chat_id=chat_id,
            settings=settings,
            request=request,
            cancel_event=cancel_event,
            stream_factory=lambda result,
            on_status,
            on_reasoning: chat_service.stream_edit_response(
                redis,
                settings,
                user_id=user.id,
                chat_id=chat_id,
                message_id=body.message_id,
                new_content=body.content,
                model_alias=body.model,
                should_cancel=cancel_event.is_set,
                result=result,
                client_timezone=body.client_timezone,
                client_location=body.client_location,
                client_latitude=body.client_latitude,
                client_longitude=body.client_longitude,
                on_status=on_status,
                on_reasoning=on_reasoning,
            ),
        ):
            yield chunk

    return _sse_response(generate())
