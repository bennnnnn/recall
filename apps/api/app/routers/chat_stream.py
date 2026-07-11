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


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _detach_finalize_tasks(result: dict[str, Any]) -> None:
    """DB finalize + job enqueue keep running as background tasks; `done` is
    sent immediately with the pre-assigned message_id instead of holding the
    stream open on Neon/Redis round trips. The finalize registry guards the
    next turn against the still-pending commit."""
    result.pop("_finalize_db_task", None)
    result.pop("_finalize_task", None)


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
        _detach_finalize_tasks(result)

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
