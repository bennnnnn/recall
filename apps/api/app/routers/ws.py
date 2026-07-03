import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.exceptions import ChatServiceError, QuotaExceededError
from app.gateways.google_auth import GoogleAuthError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.schemas import ChatMessageRequest, EditMessageRequest
from app.services import auth as auth_service
from app.services import chat as chat_service
from app.services import tokens as tokens_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    """Send a WS frame; return False if the client already disconnected."""
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


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

        if not await _safe_send_json(websocket, {"type": "stream_end"}):
            return

        finalize_task = result.pop("_finalize_db_task", None)
        if finalize_task is not None:
            try:
                await finalize_task
            except Exception:
                logger.exception("Failed to finalize chat stream")

        done: dict[str, str] = {"type": "done"}
        message_id = result.get("message_id")
        if message_id:
            done["message_id"] = message_id
        recalled = result.get("recalled")
        if recalled:
            done["recalled"] = recalled
        memory_hints = result.get("memory_hints")
        if memory_hints:
            done["memory_hints"] = memory_hints
        context_summarized = result.get("context_summarized")
        if context_summarized:
            done["context_summarized"] = context_summarized
        todos_sync = result.get("todos_sync")
        if todos_sync:
            done["todos_sync"] = todos_sync
        search_sources = result.get("search_sources")
        if search_sources:
            done["search_sources"] = search_sources
        final_content = result.get("final_content")
        if final_content:
            done["final_content"] = final_content
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
    await websocket.accept()
    settings = get_settings()
    redis = get_redis_client()

    try:
        auth_message = await websocket.receive_json()
        token = auth_message.get("token")
        if not token:
            await websocket.send_json({"type": "error", "message": "Missing token"})
            await websocket.close()
            return

        user_id = await tokens_service.verify_access_token(redis, token, settings)
        client_timezone = auth_message.get("client_timezone")
        if client_timezone is not None and not isinstance(client_timezone, str):
            client_timezone = None
    except (GoogleAuthError, json.JSONDecodeError, KeyError):
        await websocket.send_json({"type": "error", "message": "Unauthorized"})
        await websocket.close()
        return

    allowed = await allow_request(
        redis,
        f"rate:ws:{user_id}",
        limit=30,
        window_seconds=60,
    )
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

                async with SessionLocal() as session:
                    user = await auth_service.get_current_user(session, user_id)
                    if user is None:
                        await websocket.send_json({"type": "error", "message": "User not found"})
                        continue

                async def emit_status(phase: str) -> None:
                    await _safe_send_json(websocket, {"type": "status", "phase": phase})

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
                    )

                await _run_chat_stream(
                    websocket,
                    cancel_event=cancel_event,
                    stream_factory=_regen_stream,
                )
                continue

            if msg_type == "edit":
                try:
                    request = EditMessageRequest.model_validate(payload)
                except ValidationError:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid edit request"},
                    )
                    continue

                edit_model = request.model
                edit_loc = request.client_location
                edit_lat = request.client_latitude
                edit_lng = request.client_longitude

                async with SessionLocal() as session:
                    user = await auth_service.get_current_user(session, user_id)
                    if user is None:
                        await websocket.send_json({"type": "error", "message": "User not found"})
                        continue

                async def emit_status(phase: str) -> None:
                    await _safe_send_json(websocket, {"type": "status", "phase": phase})

                def _edit_stream(
                    result,
                    mid=request.message_id,
                    text=request.content,
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

            async with SessionLocal() as session:
                user = await auth_service.get_current_user(session, user_id)
                if user is None:
                    await websocket.send_json({"type": "error", "message": "User not found"})
                    continue

            async def emit_status(phase: str) -> None:
                await _safe_send_json(websocket, {"type": "status", "phase": phase})

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
                )

            await _run_chat_stream(
                websocket,
                cancel_event=cancel_event,
                stream_factory=_message_stream,
            )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected chat_id=%s", chat_id)
