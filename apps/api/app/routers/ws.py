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
from app.exceptions import ChatServiceError, QuotaExceededError
from app.gateways.google_auth import GoogleAuthError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.schemas import ChatMessageRequest, EditMessageRequest
from app.services import chat as chat_service
from app.services import tokens as tokens_service

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
        except QuotaExceededError as exc:
            await _safe_send_json(
                websocket,
                {"type": "error", "code": "quota_exceeded", "message": exc.message},
            )
            return
        except ChatServiceError as exc:
            await _safe_send_json(websocket, {"type": "error", "message": exc.message})
            return
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
            return
        except Exception:
            logger.exception("Chat stream failed")
            await _safe_send_json(
                websocket,
                {"type": "error", "message": "Something went wrong. Try again."},
            )
            return

        stream_end: dict[str, Any] = {"type": "stream_end"}
        resolved_model = result.get("resolved_model")
        if resolved_model:
            stream_end["resolved_model"] = resolved_model
        if result.get("fallback_used"):
            stream_end["fallback_used"] = result["fallback_used"]
        if not await _safe_send_json(websocket, stream_end):
            return

        # DB finalize + job enqueue run as background tasks; `done` already
        # carries the pre-assigned message_id and turn metadata, so send it
        # now instead of holding the client on Neon/Redis round trips. The
        # finalize registry guards the next turn against the pending commit.
        result.pop("_finalize_db_task", None)
        result.pop("_finalize_task", None)

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
        await _safe_send_json(websocket, done)

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
                    break
                if msg.get("type") == "cancel":
                    cancel_event.set()
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
        await producer
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
                try:
                    request = ChatMessageRequest.model_validate(payload)
                except ValidationError:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid regenerate request"},
                    )
                    continue

                regen_model = request.model
                regen_loc = request.client_location
                regen_lat = request.client_latitude
                regen_lng = request.client_longitude

                async def emit_status(phase: str) -> None:
                    await _safe_send_json(websocket, {"type": "status", "phase": phase})

                async def emit_reasoning(chunk: str) -> None:
                    await _safe_send_json(websocket, {"type": "reasoning", "content": chunk})

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
                continue

            if msg_type == "edit":
                try:
                    edit_request = EditMessageRequest.model_validate(payload)
                except ValidationError:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid edit request"},
                    )
                    continue

                edit_model = edit_request.model
                edit_loc = edit_request.client_location
                edit_lat = edit_request.client_latitude
                edit_lng = edit_request.client_longitude

                async def emit_status(phase: str) -> None:
                    await _safe_send_json(websocket, {"type": "status", "phase": phase})

                async def emit_reasoning(chunk: str) -> None:
                    await _safe_send_json(websocket, {"type": "reasoning", "content": chunk})

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
                continue

            if msg_type != "message":
                continue

            content = payload.get("content", "").strip()

            try:
                request = ChatMessageRequest.model_validate(payload)
            except ValidationError:
                await websocket.send_json({"type": "error", "message": "Invalid message"})
                continue

            if not content and not request.attachment_ids:
                continue

            message_content = content
            message_model = request.model

            async def emit_status(phase: str) -> None:
                await _safe_send_json(websocket, {"type": "status", "phase": phase})

            async def emit_reasoning(chunk: str) -> None:
                await _safe_send_json(websocket, {"type": "reasoning", "content": chunk})

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
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected chat_id=%s", chat_id)
