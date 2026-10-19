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
from redis.asyncio import Redis

from app.core import shutdown
from app.core.chat_rate_limit import allow_chat_message
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import ChatMessageRequest
from app.modules.chat import stream_entry
from app.modules.chat.finalize_registry import register_inflight_stream
from app.modules.chat.prompt_builder import StreamReasoningFn
from app.modules.chat.stream_events import (
    EXPECTED_TURN_ERRORS,
    SERVER_RESTARTING_MESSAGE,
    StreamEndEvent,
    await_finalize_commit,
    build_reasoning_event,
    build_start_event,
    build_status_event,
    build_token_event,
    clear_task_cancellation,
    finish_open_stream,
    persist_finalize_if_pending,
    pop_finalize_tasks,
    settled_turn_event,
    take_related_prompts_event,
    turn_error_payload,
)
from app.modules.chat.stream_status import StreamStatusFn
from app.modules.chat.turn_deps import default_deps
from app.modules.chat.turn_outcome import TurnOutcome

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chat-stream"])

_DISCONNECT_POLL_SECONDS = 0.5

_TokenStream = Callable[
    [TurnOutcome, StreamStatusFn, StreamReasoningFn, Callable[[], bool]],
    AsyncIterator[str],
]


async def require_chat_rate_limit(user: User = Depends(get_current_user)) -> Redis:
    """Throttle chat actions per user, then hand back the Redis handle.

    The same check guards all three streaming routes (and ws.py's own
    per-message limiter); as a dependency it is declared once instead of
    copy-pasted into every new streaming entry point.
    """
    redis = get_redis_client()
    if not await allow_chat_message(redis, user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chat requests. Try again shortly.",
            headers={"Retry-After": "60"},
        )
    return redis


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _stream_tokens_sse(
    *,
    chat_id: UUID,
    settings: Settings,
    stream_factory: _TokenStream,
    request: Request,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[str]:
    outcome = TurnOutcome()
    event_queue: asyncio.Queue[tuple[str, str, str | None] | None] = asyncio.Queue()
    producer_cancelled = False
    if cancel_event is None:
        cancel_event = asyncio.Event()
    if shutdown.stopping():
        # A turn begun now would be stopped before its first token.
        yield _sse(
            turn_error_payload(None, user_message_saved=False, message=SERVER_RESTARTING_MESSAGE)
        )
        return
    yield _sse(build_start_event())

    async def on_status(phase: str, detail: str | None = None) -> None:
        await event_queue.put(("status", phase, detail))

    async def on_reasoning(chunk: str) -> None:
        await event_queue.put(("reasoning", chunk, None))

    def should_cancel() -> bool:
        return cancel_event.is_set()

    async def produce_tokens() -> None:
        stream = stream_factory(outcome, on_status, on_reasoning, should_cancel)
        try:
            async for token_text in stream:
                if should_cancel():
                    break
                await event_queue.put(("token", token_text, None))
        except asyncio.CancelledError:
            # Cancel often lands in this task, not inside the generator.
            # The generator is then parked at yield and would never save.
            clear_task_cancellation()
            cancel_event.set()
        finally:
            await finish_open_stream(stream)
            with suppress(Exception):
                await event_queue.put(None)

    producer: asyncio.Task[None] | None = None

    def cancel_producer_once() -> None:
        nonlocal producer_cancelled
        if producer_cancelled or producer is None or producer.done():
            return
        producer_cancelled = True
        producer.cancel()

    async def watch_disconnect() -> None:
        """SSE is one-way, so a client's only way to stop generation is
        closing the connection — without this, a closed tab left the LLM
        call running to completion with tokens streamed to nobody, still
        burning quota and provider cost. `cancel_event` is also passed as
        `should_cancel` into the actual stream_entry call, so setting
        it here stops generation at the source, not just this relay.

        Cancel the producer task immediately — checking should_cancel only
        between tokens leaves an idle LiteLLM wait (up to stream timeout)
        running after disconnect.
        """
        try:
            while not cancel_event.is_set():
                if await request.is_disconnected():
                    cancel_event.set()
                    cancel_producer_once()
                    await event_queue.put(None)
                    return
                await asyncio.sleep(_DISCONNECT_POLL_SECONDS)
        except asyncio.CancelledError:
            pass

    def stop() -> None:
        """A client stops by closing the stream; a server shutdown does the same."""
        cancel_event.set()
        cancel_producer_once()

    producer = asyncio.create_task(produce_tokens())
    register_inflight_stream(chat_id, producer, stop=stop)
    disconnect_watcher = asyncio.create_task(watch_disconnect())

    try:
        while True:
            item = await event_queue.get()
            if item is None:
                break
            kind, payload, extra = item
            if kind == "status":
                yield _sse(build_status_event(payload, extra))
            elif kind == "reasoning":
                yield _sse(build_reasoning_event(payload))
            else:
                yield _sse(build_token_event(payload))

        if cancel_event.is_set():
            # Disconnect already cancelled the producer. A second cancel
            # lands in the partial-reply save and drops the text.
            with suppress(asyncio.CancelledError):
                await producer
            if not shutdown.stopping():
                return
            # The server stopped the turn; the client is still here to be told.
            if outcome.message_id is None:
                yield _sse(
                    turn_error_payload(
                        None,
                        user_message_saved=outcome.user_message_saved,
                        message=SERVER_RESTARTING_MESSAGE,
                    )
                )
                return

        with suppress(asyncio.CancelledError):
            await producer
        if producer.cancelled():
            return
        if (exc := producer.exception()) is not None:
            raise exc

        yield _sse(StreamEndEvent.from_outcome(outcome).model_dump())
        commit = await await_finalize_commit(pop_finalize_tasks(outcome))
        yield _sse(settled_turn_event(outcome, commit))
        if commit != "committed":
            return
        related = await take_related_prompts_event(outcome.related_task)
        if related is not None:
            yield _sse(related)
    except Exception as exc:
        if not isinstance(exc, EXPECTED_TURN_ERRORS):
            logger.exception("SSE chat stream failed chat_id=%s", chat_id)
        yield _sse(turn_error_payload(exc, user_message_saved=outcome.user_message_saved))
    finally:
        # The request task is cancelled when the client drops the socket.
        # That pending cancel would abort the partial-reply save on the
        # next await, and a second producer.cancel() does the same.
        clear_task_cancellation()
        cancel_event.set()
        cancel_producer_once()
        if not producer.done():
            with suppress(asyncio.CancelledError, Exception):
                await producer
        # M10: if the SSE transport failed mid-stream (client disconnect,
        # proxy drop) the success-path finalize await above never ran, so
        # the background DB commit that persists the partial assistant
        # message would be orphaned and the user's partial reply lost.
        # Await it here too (bounded) so partial tokens are saved even
        # when the transport breaks. The shield inside await_finalize_commit
        # means this never cancels the commit task on timeout.
        await persist_finalize_if_pending(outcome)
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


def _client_geo(body: ChatMessageRequest) -> dict[str, Any]:
    return {
        "client_timezone": body.client_timezone,
        "client_location": body.client_location,
        "client_latitude": body.client_latitude,
        "client_longitude": body.client_longitude,
    }


@router.post("/{chat_id}/messages/stream")
async def stream_message_sse(
    chat_id: UUID,
    body: ChatMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(require_chat_rate_limit),
) -> StreamingResponse:
    return _sse_response(
        _stream_tokens_sse(
            chat_id=chat_id,
            settings=settings,
            request=request,
            stream_factory=lambda outcome, on_status, on_reasoning, should_cancel: (
                stream_entry.stream_chat_response(
                    default_deps(),
                    redis,
                    settings,
                    user_id=user.id,
                    chat_id=chat_id,
                    content=body.content,
                    model_alias=body.model,
                    attachment_ids=body.attachment_ids or None,
                    should_cancel=should_cancel,
                    outcome=outcome,
                    on_status=on_status,
                    on_reasoning=on_reasoning,
                    user=user,
                    **_client_geo(body),
                )
            ),
        )
    )


@router.post("/{chat_id}/regenerate/stream")
async def stream_regenerate_sse(
    chat_id: UUID,
    body: ChatMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(require_chat_rate_limit),
) -> StreamingResponse:
    return _sse_response(
        _stream_tokens_sse(
            chat_id=chat_id,
            settings=settings,
            request=request,
            stream_factory=lambda outcome, on_status, on_reasoning, should_cancel: (
                stream_entry.stream_regenerate_response(
                    default_deps(),
                    redis,
                    settings,
                    user_id=user.id,
                    chat_id=chat_id,
                    model_alias=body.model,
                    should_cancel=should_cancel,
                    outcome=outcome,
                    on_status=on_status,
                    on_reasoning=on_reasoning,
                    **_client_geo(body),
                )
            ),
        )
    )
