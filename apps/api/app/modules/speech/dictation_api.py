"""HTTP for live dictation (``speech.dictation``): mint, connect, end.

The phone mints a session (one of the day's ``speech_transcription`` slots), sends its
WebRTC offer to ``/dictation/connect`` and streams the mic to OpenAI; the words come
back on the call's data channel. ``/dictation/end`` hangs the call up. A refused mint
with ``not_available`` or ``not_configured`` sends the phone to the recorded path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.consent import get_consented_user
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.models.orm import User
from app.modules.speech import dictation
from app.modules.speech.gates import (
    SpeechRefusedError,
    refund_day_on_failure,
    require_plan_feature,
    require_speech_rate,
    require_voice_spend_ok,
    reserve_day_or_raise,
)
from app.services import quota as quota_service

router = APIRouter(prefix="/speech", tags=["speech"])


class DictationSessionIn(BaseModel):
    # The app's language (``pt-BR``, ``am``): the words are transcribed in it.
    language: str | None = Field(default=None, max_length=16)


class DictationSessionOut(BaseModel):
    """A minted dictation. Its secret stays on the server: connect with ``call_id``."""

    call_id: str
    expires_at: int
    model: str
    # The server hangs the call up this long after it connects.
    max_duration_seconds: int


class DictationConnectIn(BaseModel):
    call_id: str = Field(min_length=8, max_length=128)
    sdp: str = Field(min_length=10, max_length=32_000)


class DictationConnectOut(BaseModel):
    sdp: str


class DictationEndIn(BaseModel):
    call_id: str = Field(min_length=8, max_length=128)
    # Whether any words came back: a take that heard none gives the day's slot back.
    heard: bool = True


def _require_live_dictation(settings: Settings) -> None:
    if not settings.speech_transcription_enabled or not settings.speech_live_dictation_enabled:
        raise SpeechRefusedError(
            "Not available", status_code=status.HTTP_404_NOT_FOUND, code="not_available"
        )


@router.post("/dictation/session", response_model=DictationSessionOut)
async def create_dictation_session(
    body: DictationSessionIn,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> DictationSessionOut:
    """Charge one of today's voice inputs and mint a transcription session for it."""
    _require_live_dictation(settings)
    require_plan_feature(
        user, settings, "speech_transcription", quota_service.SPEECH_NOT_IN_PLAN_MESSAGE
    )
    if not settings.openai_api_key.strip():
        # Its own code: the phone records the clip instead (a dev server's mock answers it).
        raise SpeechRefusedError(
            "Live voice input is not configured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="not_configured",
        )
    redis = get_redis_client()
    await require_voice_spend_ok(redis, settings)
    await require_speech_rate(
        redis, settings, f"speech_rl:{user.id}", quota_service.SPEECH_RATE_LIMIT_MESSAGE
    )
    day = await reserve_day_or_raise("speech_transcription", redis, user, settings)
    # A mint is not billed: any failure here gives the slot back.
    async with refund_day_on_failure("speech_transcription", redis, user.id, day):
        session = await dictation.open_session(
            redis, settings, user.id, day=day, language=body.language or user.locale
        )
    return DictationSessionOut(
        call_id=session.session_id,
        expires_at=session.expires_at,
        model=session.model,
        max_duration_seconds=session.max_duration_seconds,
    )


@router.post("/dictation/connect", response_model=DictationConnectOut)
async def connect_dictation_session(
    body: DictationConnectIn,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> DictationConnectOut:
    """The phone's WebRTC offer for a minted dictation; answers with OpenAI's SDP. Once."""
    _require_live_dictation(settings)
    answer = await dictation.connect(get_redis_client(), settings, user.id, body.call_id, body.sdp)
    return DictationConnectOut(sdp=answer)


@router.post("/dictation/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_dictation_session(
    body: DictationEndIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """The phone stopped: the server hangs the call up. Idempotent."""
    await dictation.end(get_redis_client(), settings, user.id, body.call_id, heard=body.heard)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
