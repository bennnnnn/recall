"""HTTP SSE fallback for chat streaming (WebSocket alternative for web/proxy clients)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.chat_rate_limit import allow_chat_message
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.core.redis import get_redis_client
from app.exceptions import ChatServiceError, QuotaExceededError, RedisUnavailableError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.orm import User
from app.models.schemas import ChatMessageRequest, EditMessageRequest
from app.services import chat as chat_service
from app.services.chat.prompt_builder import StreamReasoningFn
from app.services.chat.stream_events import (
    await_finalize_commit,
    build_done_payload,
    error_payload_for_exception,
    pop_finalize_tasks,
)
from app.services.chat.stream_status import StreamStatusFn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chat-stream"])

_DISCONNECT_POLL_SECONDS = 0.5


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _stream_tokens_sse(
    *,
    chat_id: UUID,
    settings: Settings,
    stream_factory: Callable[
        [dict[str, Any], StreamStatusFn, StreamReasoningFn],
        AsyncIterator[str],
    ],
    request: Request,
    cancel_event: asyncio.Event,
) -> AsyncIterator[str]:
    result: dict[str, Any] = {}
    event_queue: asyncio.Queue[tuple[str, str, str | None] | None] = asyncio.Queue()
    yield _sse({"type": "start"})

    async def on_status(phase: str, detail: str | None = None) -> None:
        await event_queue.put(("status", phase, detail))

    async def on_reasoning(chunk: str) -> None:
        await event_queue.put(("reasoning", chunk, None))

    def should_cancel() -> bool:
        return cancel_event.is_set()

    async def produce_tokens() -> None:
        try:
            stream = stream_factory(result, on_status, on_reasoning)
            async for token_text in stream:
                if should_cancel():
                    break
                await event_queue.put(("token", token_text, None))
        finally:
            await event_queue.put(None)

    producer: asyncio.Task[None] | None = None

    async def watch_disconnect() -> None:
        """SSE is one-way, so a client's only way to stop generation is
        closing the connection — without this, a closed tab left the LLM
        call running to completion with tokens streamed to nobody, still
        burning quota and provider cost. `cancel_event` is also passed as
        `should_cancel` into the actual chat_service stream call, so setting
        it here stops generation at the source, not just this relay.

        Cancel the producer task immediately — checking should_cancel only
        between tokens leaves an idle LiteLLM wait (up to stream timeout)
        running after disconnect.
        """
        try:
            while not cancel_event.is_set():
                if await request.is_disconnected():
                    cancel_event.set()
                    if producer is not None and not producer.done():
                        producer.cancel()
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
            kind, payload, extra = item
            if kind == "status":
                status_event: dict[str, Any] = {"type": "status", "phase": payload}
                if extra:
                    status_event["detail"] = extra
                yield _sse(status_event)
            elif kind == "reasoning":
                yield _sse({"type": "reasoning", "content": payload})
            else:
                yield _sse({"type": "token", "content": payload})

        if cancel_event.is_set():
            if not producer.done():
                producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer
            return

        with suppress(asyncio.CancelledError):
            await producer
        if producer.cancelled():
            return
        if (exc := producer.exception()) is not None:
            raise exc

        stream_end: dict[str, Any] = {"type": "stream_end"}
        resolved_model = result.get("resolved_model")
        if resolved_model:
            stream_end["resolved_model"] = resolved_model
        if result.get("fallback_used"):
            stream_end["fallback_used"] = result["fallback_used"]
        yield _sse(stream_end)
        finalize_db_task = pop_finalize_tasks(result)
        if not await await_finalize_commit(finalize_db_task):
            yield _sse({"type": "error", "message": "Failed to save the response. Please retry."})
            return

        yield _sse(build_done_payload(result))
    except Exception as exc:
        if not isinstance(
            exc,
            QuotaExceededError | RedisUnavailableError | ChatServiceError | ModelUnavailableError,
        ):
            logger.exception("SSE chat stream failed chat_id=%s", chat_id)
        yield _sse(error_payload_for_exception(exc))
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
    if not await allow_chat_message(redis, user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chat requests. Try again shortly.",
            headers={"Retry-After": "60"},
        )
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
    if not await allow_chat_message(redis, user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chat requests. Try again shortly.",
            headers={"Retry-After": "60"},
        )
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
    if not await allow_chat_message(redis, user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chat requests. Try again shortly.",
            headers={"Retry-After": "60"},
        )
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
