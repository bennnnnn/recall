from __future__ import annotations

import base64
import binascii
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.gateways import openai_speech_gateway
from app.models.orm import User
from app.models.schemas.integrations import SPEECH_MAX_AUDIO_BYTES, SPEECH_MAX_B64_CHARS
from app.services import live_talk as live_talk_service
from app.services import plan as plan_service
from app.services import quota as quota_service

router = APIRouter(prefix="/speech", tags=["speech"])

_STT_PROMPT = (
    "Conversational dictation for a personal AI assistant. "
    "Preserve what the speaker actually said. Do not invent closing phrases, captions, or filler."
)
_REALTIME_INSTRUCTIONS = (
    "You are Recall, a personal voice assistant. Speak naturally and respond quickly. "
    "Prefer one or two concise spoken sentences unless the user asks for detail. "
    "Do not use markdown or read punctuation aloud. Continue in the language the user is speaking."
)
_REALTIME_HISTORY_MAX = 10
_REALTIME_HISTORY_CHARS = 600


class DirectTranscriptionIn(BaseModel):
    audio_base64: str = Field(max_length=SPEECH_MAX_B64_CHARS)
    filename: str = Field(default="speech.m4a", max_length=255)
    language: str | None = Field(default=None, max_length=16)


class DirectTranscriptionOut(BaseModel):
    text: str
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
    user_text: str = Field(default="", max_length=20_000)
    assistant_text: str = Field(default="", max_length=20_000)


def _decode_audio(raw: str) -> bytes:
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio payload",
        ) from exc
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio payload")
    if len(data) > SPEECH_MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio payload too large",
        )
    return data


def _safety_identifier(user: User) -> str:
    return hashlib.sha256(f"recall:{user.id}".encode()).hexdigest()


def _realtime_instructions(history: list[tuple[str, str]] | None) -> str:
    if not history:
        return _REALTIME_INSTRUCTIONS
    lines: list[str] = []
    for role, content in history[-_REALTIME_HISTORY_MAX:]:
        if role not in {"user", "assistant"}:
            continue
        text = " ".join((content or "").split()).strip()[:_REALTIME_HISTORY_CHARS]
        if text:
            lines.append(f"{role}: {text}")
    if not lines:
        return _REALTIME_INSTRUCTIONS
    context = "\n".join(lines)
    return f"{_REALTIME_INSTRUCTIONS}\n\nRecent conversation context:\n{context}"


@router.post("/transcribe/v2", response_model=DirectTranscriptionOut)
async def transcribe_v2(
    body: DirectTranscriptionIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> DirectTranscriptionOut:
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    if not openai_speech_gateway.api_key():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Direct speech transcription is not configured",
        )

    redis = get_redis_client()
    if settings.speech_rate_limit_per_minute > 0:
        allowed = await allow_request_fail_closed(
            redis,
            f"speech_v2_rl:{user.id}",
            limit=settings.speech_rate_limit_per_minute,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.SPEECH_RATE_LIMIT_MESSAGE,
            )

    daily_limit = quota_service.speech_transcription_limit_for_user(user, settings)
    if not await quota_service.reserve_speech_transcription(redis, user.id, limit=daily_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=quota_service.speech_limit_exceeded_message(user),
        )

    data = _decode_audio(body.audio_base64)
    text = await openai_speech_gateway.transcribe(
        data,
        filename=body.filename,
        language=body.language,
        prompt=_STT_PROMPT,
    )
    if text is None:
        await quota_service.refund_speech_transcription(redis, user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not transcribe audio",
        )
    return DirectTranscriptionOut(text=text, model=openai_speech_gateway.stt_model())


@router.post("/live/webrtc", response_model=RealtimeOfferOut)
async def create_realtime_webrtc_call(
    body: RealtimeOfferIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> RealtimeOfferOut:
    if not settings.speech_live_talk_enabled or not openai_speech_gateway.realtime_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    if not plan_service.is_pro(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=quota_service.LIVE_TALK_REQUIRES_PRO_MESSAGE,
        )
    if not openai_speech_gateway.api_key():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Realtime voice is not configured",
        )

    history: list[tuple[str, str]] | None = None
    if body.chat_id is not None:
        async with SessionLocal() as session:
            loaded = await live_talk_service.load_live_talk_history(
                session,
                chat_id=body.chat_id,
                user_id=user.id,
            )
        if loaded is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        history, _ = loaded

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

    result = await openai_speech_gateway.create_realtime_call(
        offer_sdp=body.sdp,
        instructions=_realtime_instructions(history),
        safety_identifier=_safety_identifier(user),
    )
    if result is None:
        await quota_service.refund_live_talk_if_pending(redis, user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not start realtime voice",
        )
    # Realtime quota is billed once when the persistent voice session is
    # successfully established; later transcript persistence never touches it.
    await quota_service.clear_live_talk_pending(redis, user.id)
    return RealtimeOfferOut(
        sdp=result.answer_sdp,
        call_id=result.call_id,
        model=openai_speech_gateway.realtime_model(),
    )


@router.post("/live/persist", status_code=status.HTTP_204_NO_CONTENT)
async def persist_realtime_turn(
    body: RealtimePersistIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    user_text = body.user_text.strip()
    assistant_text = body.assistant_text.strip()
    if not user_text and not assistant_text:
        return

    async with SessionLocal() as session:
        loaded = await live_talk_service.load_live_talk_history(
            session,
            chat_id=body.chat_id,
            user_id=user.id,
        )
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    _, untitled = loaded

    await live_talk_service.persist_live_talk_turn(
        user=user,
        chat_id=body.chat_id,
        user_text=user_text,
        assistant_text=assistant_text,
        untitled=untitled,
        settings=settings,
        redis=get_redis_client(),
        enqueue_jobs=True,
    )
