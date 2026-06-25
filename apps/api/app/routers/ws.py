import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.gateways.google_auth import GoogleAuthError, decode_access_token
from app.models.schemas import ChatMessageRequest
from app.services import auth as auth_service
from app.services import chat as chat_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

_cancel_flags: dict[str, asyncio.Event] = {}


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

    stream_key = f"{user_id}:{chat_id}"
    cancel_event = asyncio.Event()
    _cancel_flags[stream_key] = cancel_event

    try:
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get("type")

            if msg_type == "cancel":
                cancel_event.set()
                continue

            if msg_type == "regenerate":
                cancel_event.clear()
                request = ChatMessageRequest.model_validate(payload)
                async with SessionLocal() as session:
                    user = await auth_service.get_current_user(session, user_id)
                    if user is None:
                        await websocket.send_json({"type": "error", "message": "User not found"})
                        continue
                    await websocket.send_json({"type": "start"})
                    async for token_text in chat_service.stream_regenerate_response(
                        session,
                        redis,
                        settings,
                        user=user,
                        chat_id=chat_id,
                        model_alias=request.model,
                        should_cancel=cancel_event.is_set,
                    ):
                        if cancel_event.is_set():
                            break
                        await websocket.send_json({"type": "token", "content": token_text})
                    await websocket.send_json({"type": "done"})
                continue

            if msg_type != "message":
                continue

            content = payload.get("content", "").strip()
            if not content:
                continue

            cancel_event.clear()
            request = ChatMessageRequest.model_validate(payload)

            async with SessionLocal() as session:
                user = await auth_service.get_current_user(session, user_id)
                if user is None:
                    await websocket.send_json({"type": "error", "message": "User not found"})
                    continue

                await websocket.send_json({"type": "start"})
                async for token_text in chat_service.stream_chat_response(
                    session,
                    redis,
                    settings,
                    user=user,
                    chat_id=chat_id,
                    content=content,
                    model_alias=request.model,
                    should_cancel=cancel_event.is_set,
                ):
                    if cancel_event.is_set():
                        break
                    await websocket.send_json({"type": "token", "content": token_text})
                await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected chat_id=%s", chat_id)
    finally:
        _cancel_flags.pop(stream_key, None)
