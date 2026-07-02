"""HTTP SSE fallback for chat streaming (WebSocket alternative for web/proxy clients)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.core.redis import get_redis_client
from app.exceptions import ChatServiceError, QuotaExceededError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.orm import User
from app.models.schemas import ChatMessageRequest
from app.services import chat as chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chat-stream"])


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _stream_chat_sse(
    *,
    chat_id: UUID,
    user_id: UUID,
    body: ChatMessageRequest,
    settings: Settings,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[str]:
    redis = get_redis_client()
    result: dict[str, Any] = {}
    yield _sse({"type": "start"})

    def should_cancel() -> bool:
        return cancel_event.is_set() if cancel_event is not None else False

    try:
        stream = chat_service.stream_chat_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            content=body.content,
            model_alias=body.model,
            attachment_ids=body.attachment_ids or None,
            should_cancel=should_cancel,
            result=result,
            client_timezone=body.client_timezone,
            client_location=body.client_location,
            client_latitude=body.client_latitude,
            client_longitude=body.client_longitude,
        )
        async for token_text in stream:
            if should_cancel():
                break
            yield _sse({"type": "token", "content": token_text})

        yield _sse({"type": "stream_end"})

        finalize_task = result.pop("_finalize_db_task", None)
        if finalize_task is not None:
            try:
                await finalize_task
            except Exception:
                logger.exception("Failed to finalize SSE chat stream")

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


@router.post("/{chat_id}/messages/stream")
async def stream_message_sse(
    chat_id: UUID,
    body: ChatMessageRequest,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        async for chunk in _stream_chat_sse(
            chat_id=chat_id,
            user_id=user.id,
            body=body,
            settings=settings,
        ):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
