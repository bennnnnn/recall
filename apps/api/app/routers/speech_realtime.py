from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.gateways import openai_speech_gateway
from app.models.orm import User
from app.models.schemas import MessageOut
from app.services import live_talk as live_talk_service
from app.services import plan as plan_service
from app.services import quota as quota_service

router = APIRouter(prefix="/speech", tags=["speech"])


class RealtimeSessionIn(BaseModel):
    chat_id: UUID | None = None
    barge_in: bool = False
    tools_enabled: bool = False


class RealtimeSessionOut(BaseModel):
    client_secret: str
    expires_at: int
    call_id: str
    model: str


class RealtimeOfferIn(BaseModel):
    sdp: str = Field(min_length=20, max_length=200_000)
    chat_id: UUID | None = None


class RealtimeOfferOut(BaseModel):
    sdp: str
    call_id: str | None = None
    model: str


class RealtimePersistIn(BaseModel):
    chat_id: UUID
    call_id: str = Field(min_length=8, max_length=128)
    user_text: str = Field(default="", max_length=20_000)
    assistant_text: str = Field(default="", max_length=20_000)
    turn_id: str | None = Field(default=None, max_length=128)
    return_messages: bool = False


class RealtimeToolIn(BaseModel):
    chat_id: UUID
    call_id: str = Field(min_length=8, max_length=128)
    turn_id: str = Field(min_length=1, max_length=128)
    name: Literal["memory_lookup", "web_search"]
    query: str = Field(min_length=1, max_length=500)


def _safety_identifier(user: User) -> str:
    return hashlib.sha256(f"recall:{user.id}".encode()).hexdigest()


def _realtime_instructions(
    history: list[tuple[str, str]] | None,
    *,
    memory_block: str = "",
    custom_instructions: str = "",
) -> str:
    return live_talk_service.build_realtime_instructions(
        history,
        memory_block=memory_block,
        custom_instructions=custom_instructions,
    )


async def _load_session_context_or_404(
    chat_id: UUID | None,
    user: User,
    settings: Settings,
) -> tuple[list[tuple[str, str]] | None, str]:
    loaded = await live_talk_service.load_live_talk_session_context(
        chat_id=chat_id,
        user=user,
        settings=settings,
    )
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return loaded


async def _reserve_realtime_or_raise(user: User, settings: Settings):
    if not settings.speech_live_talk_enabled or not settings.speech_realtime_voice_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    if not plan_service.is_pro(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=quota_service.LIVE_TALK_REQUIRES_PRO_MESSAGE,
        )
    if not settings.openai_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Realtime voice is not configured",
        )

    redis = get_redis_client()
    if settings.speech_rate_limit_per_minute > 0:
        allowed = await allow_request_fail_closed(
            redis,
            f"speech_realtime_rl:{user.id}",
            limit=settings.speech_rate_limit_per_minute,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.LIVE_TALK_RATE_LIMIT_MESSAGE,
            )

    daily_limit = quota_service.live_talk_limit_for_user(user, settings)
    if not await quota_service.reserve_live_talk(redis, user.id, limit=daily_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=quota_service.live_talk_limit_exceeded_message(user),
        )
    return redis


@router.post("/live/session", response_model=RealtimeSessionOut)
async def create_realtime_session(
    body: RealtimeSessionIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> RealtimeSessionOut:
    """Mint a short-lived key; mobile completes WebRTC directly with OpenAI."""
    history, memory_block = await _load_session_context_or_404(body.chat_id, user, settings)
    redis = await _reserve_realtime_or_raise(user, settings)

    result = await openai_speech_gateway.create_realtime_client_secret(
        settings,
        instructions=_realtime_instructions(
            history,
            memory_block=memory_block,
            custom_instructions=live_talk_service.voice_custom_instructions(user),
        ),
        safety_identifier=_safety_identifier(user),
        barge_in=body.barge_in,
        tools_enabled=body.tools_enabled,
    )
    if result is None:
        await quota_service.refund_live_talk_if_pending(redis, user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not start realtime voice",
        )

    session_id = await live_talk_service.issue_realtime_session(redis, user.id, body.chat_id)
    await quota_service.clear_live_talk_pending(redis, user.id)
    return RealtimeSessionOut(
        client_secret=result.value,
        expires_at=result.expires_at,
        call_id=session_id,
        model=openai_speech_gateway.realtime_model(settings),
    )


@router.post("/live/webrtc", response_model=RealtimeOfferOut)
async def create_realtime_webrtc_call(
    body: RealtimeOfferIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> RealtimeOfferOut:
    """Reject stale clients that still use the removed server-proxied SDP transport."""
    raise HTTPException(
        status_code=status.HTTP_426_UPGRADE_REQUIRED,
        detail=(
            "Legacy Live Talk client detected. Pull the latest main branch, restart Metro "
            "with a cleared cache, and reopen the dev client."
        ),
    )


@router.post("/live/persist")
async def persist_realtime_turn(
    body: RealtimePersistIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    if not settings.speech_live_talk_enabled or not settings.speech_realtime_voice_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    user_text = body.user_text.strip()
    assistant_text = body.assistant_text.strip()
    # Defense in depth: a Realtime assistant message is never a Recall turn
    # unless the mobile client first accepted a real user transcription.
    if not user_text:
        return Response(status_code=204)

    redis = get_redis_client()
    if not await live_talk_service.realtime_session_is_active(redis, user.id, body.call_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Realtime session is not active",
        )

    async with SessionLocal() as session:
        loaded = await live_talk_service.load_live_talk_history(
            session,
            chat_id=body.chat_id,
            user_id=user.id,
        )
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    _, untitled = loaded

    if body.turn_id and assistant_text:
        from app.services.live_talk_tools import search_sources_for_turn

        sources = await search_sources_for_turn(redis, user.id, body.call_id, body.turn_id)
        if sources:
            assistant_text += "\n\n```sources\n" + json.dumps(sources) + "\n```"

    user_message, assistant_message = await live_talk_service.persist_live_talk_turn(
        user=user,
        chat_id=body.chat_id,
        user_text=user_text,
        assistant_text=assistant_text,
        untitled=untitled,
        settings=settings,
        redis=redis,
        enqueue_jobs=True,
    )
    if body.return_messages:
        return JSONResponse(
            {
                "user_message": MessageOut.model_validate(user_message).model_dump(mode="json")
                if user_message
                else None,
                "assistant_message": MessageOut.model_validate(assistant_message).model_dump(
                    mode="json"
                )
                if assistant_message
                else None,
            }
        )
    return Response(status_code=204)


@router.post("/live/tool")
async def execute_realtime_tool(
    body: RealtimeToolIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    from app.repositories import chats as chats_repo
    from app.services.live_talk_tools import execute_tool

    if not settings.speech_live_talk_enabled or not settings.speech_realtime_voice_enabled:
        raise HTTPException(status_code=404, detail="Not available")
    if not plan_service.is_pro(user):
        raise HTTPException(status_code=403, detail="Live Talk requires Pro")
    redis = get_redis_client()
    bound_chat = await redis.get(live_talk_service._realtime_session_key(user.id, body.call_id))
    if isinstance(bound_chat, bytes):
        bound_chat = bound_chat.decode()
    if bound_chat != str(body.chat_id):
        raise HTTPException(status_code=403, detail="Realtime session is not active for this chat")
    if not await allow_request_fail_closed(
        redis, f"live_tools:{user.id}", limit=20, window_seconds=60
    ):
        raise HTTPException(status_code=429, detail="Voice lookups are temporarily rate limited")
    async with SessionLocal() as session:
        if await chats_repo.get_by_id(session, body.chat_id, user.id) is None:
            raise HTTPException(status_code=404, detail="Chat not found")
    return await execute_tool(
        settings,
        redis,
        user=user,
        call_id=body.call_id,
        turn_id=body.turn_id,
        name=body.name,
        query=body.query,
    )
