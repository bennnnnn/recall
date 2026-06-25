import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.exceptions import ChatServiceError
from app.gateways.google_auth import GoogleAuthError, decode_access_token
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.schemas import ChatMessageRequest
from app.services import auth as auth_service
from app.services import chat as chat_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

_cancel_flags: dict[str, asyncio.Event] = {}


async def _stream_over_ws(
    websocket: WebSocket,
    stream: AsyncIterator[str],
    cancel_event: asyncio.Event,
) -> None:
    async def run_stream() -> None:
        async for token_text in stream:
            if cancel_event.is_set():
                break
            await websocket.send_json({"type": "token", "content": token_text})
        await websocket.send_json({"type": "done"})

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
    user_id: UUID,
    chat_id: UUID,
    cancel_event: asyncio.Event,
    stream_factory: Callable[[], AsyncIterator[str]],
) -> None:
    cancel_event.clear()
    await websocket.send_json({"type": "start"})
    try:
        await _stream_over_ws(websocket, stream_factory(), cancel_event)
    except ChatServiceError as exc:
        await websocket.send_json({"type": "error", "message": exc.message})
    except ModelUnavailableError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})


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

        user_id = decode_access_token(token, settings)
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
        await websocket.send_json({"type": "error", "message": "Too many requests. Try again shortly."})
        await websocket.close()
        return

    stream_key = f"{user_id}:{chat_id}"
    cancel_event = asyncio.Event()
    _cancel_flags[stream_key] = cancel_event

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

                async with SessionLocal() as session:
                    user = await auth_service.get_current_user(session, user_id)
                    if user is None:
                        await websocket.send_json({"type": "error", "message": "User not found"})
                        continue

                def _regen_stream(model=regen_model):
                    return chat_service.stream_regenerate_response(
                        redis,
                        settings,
                        user_id=user_id,
                        chat_id=chat_id,
                        model_alias=model,
                        should_cancel=cancel_event.is_set,
                    )

                await _run_chat_stream(
                    websocket,
                    user_id=user_id,
                    chat_id=chat_id,
                    cancel_event=cancel_event,
                    stream_factory=_regen_stream,
                )
                continue

            if msg_type != "message":
                continue

            content = payload.get("content", "").strip()
            if not content:
                continue

            try:
                request = ChatMessageRequest.model_validate(payload)
            except ValidationError:
                await websocket.send_json({"type": "error", "message": "Invalid message"})
                continue

            message_content = content
            message_model = request.model

            async with SessionLocal() as session:
                user = await auth_service.get_current_user(session, user_id)
                if user is None:
                    await websocket.send_json({"type": "error", "message": "User not found"})
                    continue

            def _message_stream(text=message_content, model=message_model):
                return chat_service.stream_chat_response(
                    redis,
                    settings,
                    user_id=user_id,
                    chat_id=chat_id,
                    content=text,
                    model_alias=model,
                    should_cancel=cancel_event.is_set,
                )

            await _run_chat_stream(
                websocket,
                user_id=user_id,
                chat_id=chat_id,
                cancel_event=cancel_event,
                stream_factory=_message_stream,
            )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected chat_id=%s", chat_id)
    finally:
        _cancel_flags.pop(stream_key, None)
