import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.client_ip import client_ip_from_websocket
from app.core.config import get_settings
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.exceptions import ChatServiceError, QuotaExceededError, RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.schemas import ChatMessageRequest, EditMessageRequest
from app.services import chat as chat_service
from app.services import tokens as tokens_service
from app.services.chat.stream_events import (
    await_finalize_commit,
    build_done_payload,
    error_payload_for_exception,
    pop_finalize_tasks,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

_WS_MSG_RATE_LIMIT = 30
_WS_MSG_WINDOW_SECONDS = 60
_WS_CONNECT_RATE_LIMIT = 30
_WS_HANDSHAKE_RATE_LIMIT = 60  # unauthenticated connects per IP per minute
# Drop sockets that connect but never send the auth frame (resource leak).
_WS_AUTH_TIMEOUT_SECONDS = 10.0
_CHARGEABLE_WS_TYPES = frozenset({"message", "regenerate", "edit"})


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    """Send a WS frame; return False if the client already disconnected."""
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


async def _ws_rate_limit(redis, user_id: UUID) -> bool:
    """Per-message throttle for chat actions on an open WebSocket."""
    return await allow_request(
        redis,
        f"rate:ws:msg:{user_id}",
        limit=_WS_MSG_RATE_LIMIT,
        window_seconds=_WS_MSG_WINDOW_SECONDS,
    )


async def _ws_connect_rate_limit(redis, user_id: UUID) -> bool:
    """Limit new WebSocket handshakes per user (separate from per-message limits)."""
    return await allow_request(
        redis,
        f"rate:ws:connect:{user_id}",
        limit=_WS_CONNECT_RATE_LIMIT,
        window_seconds=_WS_MSG_WINDOW_SECONDS,
    )


async def _ws_handshake_rate_limit(redis, websocket: WebSocket) -> bool:
    """Cap unauthenticated connect attempts by client IP before accept().

    Uses the shared `client_ip_from_websocket` resolver so a Fly-proxied
    handshake is keyed on the edge-seen IP (fly-client-ip / XFF), not the
    proxy's — otherwise every connect shares one proxy's bucket.
    """
    settings = get_settings()
    ip = client_ip_from_websocket(websocket, settings)
    return await allow_request(
        redis,
        f"rate:ws:handshake:{ip}",
        limit=_WS_HANDSHAKE_RATE_LIMIT,
        window_seconds=_WS_MSG_WINDOW_SECONDS,
    )


async def _stream_over_ws(
    websocket: WebSocket,
    stream: AsyncIterator[str],
    cancel_event: asyncio.Event,
    result: dict[str, Any],
) -> None:
    async def run_stream() -> None:
        try:
            async for token_text in stream:
                if cancel_event.is_set():
                    break
                if not await _safe_send_json(websocket, {"type": "token", "content": token_text}):
                    cancel_event.set()
                    break
        except asyncio.CancelledError:
            # Task cancel interrupts an in-flight LiteLLM wait; still fall
            # through to stream_end/done so the client gets a clean stop.
            cancel_event.set()
        except Exception as exc:
            if not isinstance(exc, QuotaExceededError | ChatServiceError | ModelUnavailableError):
                logger.exception("Chat stream failed")
            await _safe_send_json(websocket, error_payload_for_exception(exc))
            return

        stream_end: dict[str, Any] = {"type": "stream_end"}
        resolved_model = result.get("resolved_model")
        if resolved_model:
            stream_end["resolved_model"] = resolved_model
        if result.get("fallback_used"):
            stream_end["fallback_used"] = result["fallback_used"]
        if not await _safe_send_json(websocket, stream_end):
            return

        # Await the DB commit before sending `done` so the message_id we hand
        # the client always references a persisted row. The token stream is
        # already flushed (stream_end above), so only the final `done` event
        # waits on the commit — streaming latency is unchanged. If the commit
        # FAILED we send an error instead of a ghost `done` with a fake id.
        finalize_db_task = pop_finalize_tasks(result)
        if not await await_finalize_commit(finalize_db_task):
            await _safe_send_json(
                websocket,
                {"type": "error", "message": "Failed to save the response. Please retry."},
            )
            return

        await _safe_send_json(websocket, build_done_payload(result))

    producer = asyncio.create_task(run_stream())
    try:
        while not producer.done():
            receiver = asyncio.create_task(websocket.receive_json())
            done, _pending = await asyncio.wait(
                {producer, receiver},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if receiver in done:
                try:
                    msg = receiver.result()
                except WebSocketDisconnect:
                    cancel_event.set()
                    if not producer.done():
                        producer.cancel()
                    break
                if msg.get("type") == "cancel":
                    cancel_event.set()
                    # Interrupt in-flight LiteLLM wait, not only between tokens.
                    if not producer.done():
                        producer.cancel()
                elif msg.get("type") != "ping":
                    await _safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "code": "busy",
                            "message": "Still generating — wait or cancel first.",
                        },
                    )
            else:
                receiver.cancel()
                try:
                    await receiver
                except asyncio.CancelledError:
                    pass
        if cancel_event.is_set() and not producer.done():
            producer.cancel()
        try:
            await producer
        except asyncio.CancelledError:
            pass
    except WebSocketDisconnect:
        cancel_event.set()
        if not producer.done():
            producer.cancel()
            try:
                await producer
            except asyncio.CancelledError:
                pass


async def _run_chat_stream(
    websocket: WebSocket,
    *,
    cancel_event: asyncio.Event,
    stream_factory: Callable[[dict[str, str]], AsyncIterator[str]],
) -> None:
    cancel_event.clear()
    if not await _safe_send_json(websocket, {"type": "start"}):
        return
    result: dict[str, str] = {}
    try:
        await _stream_over_ws(websocket, stream_factory(result), cancel_event, result)
    except QuotaExceededError as exc:
        await _safe_send_json(
            websocket,
            {"type": "error", "code": "quota_exceeded", "message": exc.message},
        )
    except RedisUnavailableError as exc:
        await _safe_send_json(
            websocket,
            {"type": "error", "code": "unavailable", "message": exc.message},
        )
    except ChatServiceError as exc:
        await _safe_send_json(websocket, {"type": "error", "message": exc.message})
    except ModelUnavailableError as exc:
        await _safe_send_json(
            websocket,
            {
                "type": "error",
                "code": exc.code,
                "message": exc.message,
                "failed_model": exc.failed_alias,
            },
        )
    except Exception:
        logger.exception("Unexpected chat stream error")
        await _safe_send_json(
            websocket,
            {"type": "error", "message": "Something went wrong. Try again."},
        )


def _status_emitters(websocket: WebSocket) -> tuple[Any, Any]:
    """Shared status/reasoning WS emitters for chargeable chat actions."""

    async def emit_status(phase: str, detail: str | None = None) -> None:
        payload = {"type": "status", "phase": phase}
        if detail:
            payload["detail"] = detail
        await _safe_send_json(websocket, payload)

    async def emit_reasoning(chunk: str) -> None:
        await _safe_send_json(websocket, {"type": "reasoning", "content": chunk})

    return emit_status, emit_reasoning


async def _handle_regenerate(
    websocket: WebSocket,
    *,
    redis: Any,
    settings: Any,
    user_id: UUID,
    chat_id: UUID,
    payload: dict[str, Any],
    client_timezone: str | None,
    cancel_event: asyncio.Event,
    emit_status: Any,
    emit_reasoning: Any,
) -> None:
    try:
        request = ChatMessageRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json(
            {"type": "error", "message": "Invalid regenerate request"},
        )
        return

    regen_model = request.model
    regen_loc = request.client_location
    regen_lat = request.client_latitude
    regen_lng = request.client_longitude

    def _regen_stream(
        result,
        model=regen_model,
        tz=client_timezone,
        loc=regen_loc,
        lat=regen_lat,
        lng=regen_lng,
    ):
        return chat_service.stream_regenerate_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            model_alias=model,
            should_cancel=cancel_event.is_set,
            result=result,
            client_timezone=tz,
            client_location=loc,
            client_latitude=lat,
            client_longitude=lng,
            on_status=emit_status,
            on_reasoning=emit_reasoning,
        )

    await _run_chat_stream(
        websocket,
        cancel_event=cancel_event,
        stream_factory=_regen_stream,
    )


async def _handle_edit(
    websocket: WebSocket,
    *,
    redis: Any,
    settings: Any,
    user_id: UUID,
    chat_id: UUID,
    payload: dict[str, Any],
    client_timezone: str | None,
    cancel_event: asyncio.Event,
    emit_status: Any,
    emit_reasoning: Any,
) -> None:
    try:
        edit_request = EditMessageRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json(
            {"type": "error", "message": "Invalid edit request"},
        )
        return

    edit_model = edit_request.model
    edit_loc = edit_request.client_location
    edit_lat = edit_request.client_latitude
    edit_lng = edit_request.client_longitude

    def _edit_stream(
        result,
        mid=edit_request.message_id,
        text=edit_request.content,
        model=edit_model,
        tz=client_timezone,
        loc=edit_loc,
        lat=edit_lat,
        lng=edit_lng,
    ):
        return chat_service.stream_edit_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            message_id=mid,
            new_content=text,
            model_alias=model,
            should_cancel=cancel_event.is_set,
            result=result,
            client_timezone=tz,
            client_location=loc,
            client_latitude=lat,
            client_longitude=lng,
            on_status=emit_status,
            on_reasoning=emit_reasoning,
        )

    await _run_chat_stream(
        websocket,
        cancel_event=cancel_event,
        stream_factory=_edit_stream,
    )


async def _handle_message(
    websocket: WebSocket,
    *,
    redis: Any,
    settings: Any,
    user_id: UUID,
    chat_id: UUID,
    payload: dict[str, Any],
    client_timezone: str | None,
    cancel_event: asyncio.Event,
    emit_status: Any,
    emit_reasoning: Any,
) -> None:
    content = payload.get("content", "").strip()

    try:
        request = ChatMessageRequest.model_validate(payload)
    except ValidationError:
        await websocket.send_json({"type": "error", "message": "Invalid message"})
        return

    if not content and not request.attachment_ids:
        return

    message_content = content
    message_model = request.model

    def _message_stream(
        result,
        text=message_content,
        model=message_model,
        aids=request.attachment_ids,
        tz=client_timezone,
        loc=request.client_location,
        lat=request.client_latitude,
        lng=request.client_longitude,
    ):
        return chat_service.stream_chat_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            content=text,
            model_alias=model,
            attachment_ids=aids,
            should_cancel=cancel_event.is_set,
            result=result,
            client_timezone=tz,
            client_location=loc,
            client_latitude=lat,
            client_longitude=lng,
            on_status=emit_status,
            on_reasoning=emit_reasoning,
        )

    await _run_chat_stream(
        websocket,
        cancel_event=cancel_event,
        stream_factory=_message_stream,
    )


@router.websocket("/ws/chats/{chat_id}")
async def chat_websocket(
    websocket: WebSocket,
    chat_id: UUID,
) -> None:
    settings = get_settings()
    redis = get_redis_client()
    try:
        if not await _ws_handshake_rate_limit(redis, websocket):
            await websocket.close(code=1008)
            return
    except Exception:
        # Fail closed: a Redis outage must not let unauthenticated connects
        # through unbounded. Close with policy-violation (1008) so the client
        # backs off and reconnects once the limiter is healthy again.
        logger.warning("WS handshake rate limit check failed; failing closed", exc_info=True)
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        auth_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=_WS_AUTH_TIMEOUT_SECONDS,
        )
        token = auth_message.get("token")
        if not token:
            await websocket.send_json({"type": "error", "message": "Missing token"})
            await websocket.close()
            return

        user_id = await tokens_service.verify_access_token(redis, token, settings)
        client_timezone = auth_message.get("client_timezone")
        if client_timezone is not None and not isinstance(client_timezone, str):
            client_timezone = None
    except TimeoutError:
        await _safe_send_json(websocket, {"type": "error", "message": "Auth timeout"})
        await websocket.close()
        return
    except RedisUnavailableError as exc:
        await _safe_send_json(
            websocket,
            {"type": "error", "code": "unavailable", "message": exc.message},
        )
        # 1013 Try Again Later — client should back off, not treat as auth failure.
        await websocket.close(code=1013)
        return
    except (GoogleAuthError, json.JSONDecodeError, KeyError):
        await websocket.send_json({"type": "error", "message": "Unauthorized"})
        await websocket.close()
        return

    allowed = await _ws_connect_rate_limit(redis, user_id)
    if not allowed:
        await websocket.send_json(
            {"type": "error", "message": "Too many requests. Try again shortly."},
        )
        await websocket.close()
        return

    cancel_event = asyncio.Event()
    emit_status, emit_reasoning = _status_emitters(websocket)

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = payload.get("type")

            if msg_type == "cancel":
                cancel_event.set()
                continue

            if msg_type in _CHARGEABLE_WS_TYPES and not await _ws_rate_limit(redis, user_id):
                await websocket.send_json(
                    {"type": "error", "message": "Too many requests. Try again shortly."},
                )
                continue

            if msg_type == "regenerate":
                await _handle_regenerate(
                    websocket,
                    redis=redis,
                    settings=settings,
                    user_id=user_id,
                    chat_id=chat_id,
                    payload=payload,
                    client_timezone=client_timezone,
                    cancel_event=cancel_event,
                    emit_status=emit_status,
                    emit_reasoning=emit_reasoning,
                )
                continue

            if msg_type == "edit":
                await _handle_edit(
                    websocket,
                    redis=redis,
                    settings=settings,
                    user_id=user_id,
                    chat_id=chat_id,
                    payload=payload,
                    client_timezone=client_timezone,
                    cancel_event=cancel_event,
                    emit_status=emit_status,
                    emit_reasoning=emit_reasoning,
                )
                continue

            if msg_type != "message":
                continue

            await _handle_message(
                websocket,
                redis=redis,
                settings=settings,
                user_id=user_id,
                chat_id=chat_id,
                payload=payload,
                client_timezone=client_timezone,
                cancel_event=cancel_event,
                emit_status=emit_status,
                emit_reasoning=emit_reasoning,
            )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected chat_id=%s", chat_id)
