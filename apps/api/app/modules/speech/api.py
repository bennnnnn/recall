import base64
import binascii
import json
import logging
from collections.abc import AsyncIterator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.core.request_limits import reject_oversized
from app.models.orm import User
from app.modules.account.consent import get_consented_user
from app.modules.speech import live_talk as live_talk_service
from app.modules.speech import service as speech_service
from app.modules.speech.gates import (
    RefundDayOnFailure,
    require_plan_feature,
    require_speech_rate,
    require_voice_spend_ok,
    reserve_day_or_raise,
)
from app.modules.speech.schemas import (
    SPEECH_MAX_AUDIO_BYTES,
    SPEECH_MAX_REQUEST_BYTES,
    SpeechLiveStatusOut,
    SpeechTranscriptionIn,
    SpeechTranscriptionOut,
    SpeechTtsIn,
    SpeechTtsOut,
)
from app.modules.speech.tts_followup import (
    normalize_tts_part,
    store_tts_followup,
    try_consume_tts_followup,
    tts_followup_key,
    tts_lead_hash,
)
from app.services import quota as quota_service
from app.services.quota import counters

router = APIRouter(prefix="/speech", tags=["speech"])
logger = logging.getLogger(__name__)

TTS_STREAM_MEDIA_TYPE = "audio/L16;rate=24000;channels=1"


def _raise_live_talk_route_gone(settings: Settings) -> None:
    if not settings.speech_live_talk_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Live talk is metered in minutes: POST /speech/live/session, then /speech/live/end",
    )


async def _reserve_tts_or_raise(user: User, settings: Settings) -> date:
    """Every TTS gate, then today's slot; returns the day it charged."""
    require_plan_feature(user, settings, "speech_tts", quota_service.SPEECH_TTS_NOT_IN_PLAN_MESSAGE)
    redis = get_redis_client()
    await require_voice_spend_ok(redis, settings)
    await require_speech_rate(
        redis, settings, f"speech_tts_rl:{user.id}", quota_service.SPEECH_TTS_RATE_LIMIT_MESSAGE
    )
    return await reserve_day_or_raise("speech_tts", redis, user, settings)


async def _aiter_nonempty(chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    async for chunk in chunks:
        if chunk:
            yield chunk


def _reject_oversized_audio(data: bytes) -> None:
    if len(data) > SPEECH_MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio payload too large",
        )


async def _transcribe_bytes(
    settings: Settings,
    data: bytes,
    filename: str,
    language: str | None = None,
) -> SpeechTranscriptionOut:
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    text = await speech_service.transcribe_audio(
        settings, data, filename=filename, language=language
    )
    if text is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not transcribe audio",
        )
    return SpeechTranscriptionOut(text=text)


@router.post("/tts", response_model=SpeechTtsOut)
async def synthesize_speech(
    body: SpeechTtsIn,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechTtsOut:
    if not settings.speech_tts_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    require_plan_feature(user, settings, "speech_tts", quota_service.SPEECH_TTS_NOT_IN_PLAN_MESSAGE)

    redis = get_redis_client()
    await require_voice_spend_ok(redis, settings)
    part = normalize_tts_part(body.part)
    reserved_day: date | None = None
    followup_key = tts_followup_key(user.id)
    consumed_followup = False
    lead_hash = (body.lead_hash or "").strip()
    if part == "rest":
        consumed_followup = await try_consume_tts_followup(
            redis, followup_key, len(body.text), lead_hash
        )
    # Same utterance as the lead: short clips within the char budget share one slot.
    billed = not consumed_followup
    if billed:
        await require_speech_rate(
            redis,
            settings,
            f"speech_tts_rl:{user.id}",
            quota_service.SPEECH_TTS_RATE_LIMIT_MESSAGE,
        )
        reserved_day = await reserve_day_or_raise("speech_tts", redis, user, settings)

    async with RefundDayOnFailure("speech_tts", redis, user.id, reserved_day):
        alias = speech_service.normalize_tts_alias(body.model)
        result = await speech_service.synthesize_speech(
            settings,
            body.text,
            language=body.language,
            model_alias=alias,
            voice=user.tts_voice,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not synthesize speech",
            )
        audio_bytes, content_type = result
        if part == "lead":
            await store_tts_followup(redis, followup_key, body.text)
        if billed:
            await quota_service.record_voice_spend(redis, quota_service.TTS_SPEND_USD)
        return SpeechTtsOut(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            content_type=content_type,
            model=alias,
            lead_hash=tts_lead_hash(body.text) if part == "lead" else None,
        )


@router.post("/tts/stream")
async def stream_speech(
    body: SpeechTtsIn,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> StreamingResponse:
    if not settings.speech_tts_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    day = await _reserve_tts_or_raise(user, settings)
    redis = get_redis_client()
    alias = speech_service.normalize_tts_alias(body.model)

    async def body_iter() -> AsyncIterator[bytes]:
        got = False
        try:
            async for chunk in _aiter_nonempty(
                speech_service.iter_tts_pcm(
                    settings,
                    body.text,
                    language=body.language,
                    model_alias=alias,
                    voice=user.tts_voice,
                )
            ):
                got = True
                yield chunk
        finally:
            if not got:
                await counters.refund("speech_tts", redis, user.id, day=day)
            else:
                await quota_service.record_voice_spend(redis, quota_service.TTS_SPEND_USD)

    return StreamingResponse(
        body_iter(),
        media_type=TTS_STREAM_MEDIA_TYPE,
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "X-Recall-Tts-Model": alias,
        },
    )


@router.post("/transcribe", response_model=SpeechTranscriptionOut)
async def transcribe_speech(
    request: Request,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechTranscriptionOut:
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    # Plan before the body: a refused user never uploads or parses audio.
    require_plan_feature(
        user, settings, "speech_transcription", quota_service.SPEECH_NOT_IN_PLAN_MESSAGE
    )

    # Size first — a 6MB clip used to pass the 7.5MB body cap, reserve quota,
    # then fail as 502 when the service rejected at 5MB.
    content_type = request.headers.get("content-type", "")
    language: str | None = None
    if "application/json" in content_type:
        reject_oversized(request, b"", SPEECH_MAX_REQUEST_BYTES, "Audio payload too large")
        try:
            raw = await request.body()
            reject_oversized(request, raw, SPEECH_MAX_REQUEST_BYTES, "Audio payload too large")
            payload = SpeechTranscriptionIn.model_validate(json.loads(raw))
            data = base64.b64decode(payload.audio_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio payload",
            ) from exc
        _reject_oversized_audio(data)
        filename = payload.filename
        language = payload.language
    else:
        # Multipart: check Content-Length BEFORE request.form() parses the body.
        reject_oversized(request, b"", SPEECH_MAX_REQUEST_BYTES, "Audio payload too large")
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing audio file",
            )
        declared_size = getattr(upload, "size", None)
        if declared_size is not None and int(declared_size) > SPEECH_MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio payload too large",
            )
        data = await upload.read()  # type: ignore[union-attr]
        _reject_oversized_audio(data)
        filename = getattr(upload, "filename", None) or "speech.m4a"

    redis = get_redis_client()
    await require_voice_spend_ok(redis, settings)
    await require_speech_rate(
        redis, settings, f"speech_rl:{user.id}", quota_service.SPEECH_RATE_LIMIT_MESSAGE
    )
    day = await reserve_day_or_raise("speech_transcription", redis, user, settings)

    async with RefundDayOnFailure("speech_transcription", redis, user.id, day):
        result = await _transcribe_bytes(settings, data, filename, language)
        await quota_service.record_voice_spend(redis, quota_service.STT_SPEND_USD)
        return result


@router.get("/live", response_model=SpeechLiveStatusOut)
async def live_talk_status(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveStatusOut:
    if not settings.speech_live_talk_enabled:
        return SpeechLiveStatusOut(enabled=False, entitled=False, remaining=0, limit=0)
    return await live_talk_service.live_talk_status(get_redis_client(), user, settings)


@router.post("/live/turn")
async def live_talk_turn(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Gone — speak self-reserves. Stale clients get 410 instead of a second slot."""
    _raise_live_talk_route_gone(settings)


@router.post("/live/refund")
async def live_talk_refund(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Gone — minutes settle on POST /speech/live/end, not per turn."""
    _raise_live_talk_route_gone(settings)


@router.post("/live/commit")
async def live_talk_commit(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Gone — Live Talk is WebRTC (`POST /speech/live/session`)."""
    _raise_live_talk_route_gone(settings)


@router.post("/live/speak")
async def live_talk_speak(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Gone — Live Talk is WebRTC (`POST /speech/live/session`)."""
    _raise_live_talk_route_gone(settings)
