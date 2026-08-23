import base64
import binascii
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep, redis_unavailable_http_exception
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.models.schemas import (
    SpeechLiveSpeakIn,
    SpeechLiveSpeakOut,
    SpeechLiveStatusOut,
    SpeechTranscriptionIn,
    SpeechTranscriptionOut,
    SpeechTtsIn,
    SpeechTtsOut,
)
from app.models.schemas.integrations import SPEECH_MAX_AUDIO_BYTES, SPEECH_MAX_REQUEST_BYTES
from app.services import plan as plan_service
from app.services import quota as quota_service
from app.services import speech as speech_service

router = APIRouter(prefix="/speech", tags=["speech"])

TTS_STREAM_MEDIA_TYPE = "audio/L16;rate=24000;channels=1"


async def _live_talk_status(
    user: User,
    settings: Settings,
    *,
    refunded: bool = False,
) -> SpeechLiveStatusOut:
    redis = get_redis_client()
    limit = quota_service.live_talk_limit_for_user(user, settings)
    used = await quota_service.live_talk_used(redis, user.id)
    remaining = max(0, limit - used)
    enabled = settings.speech_live_talk_enabled
    entitled = enabled and plan_service.is_pro(user)
    return SpeechLiveStatusOut(
        enabled=enabled,
        entitled=entitled,
        remaining=remaining,
        limit=limit,
        refunded=refunded,
    )


async def _reserve_tts_or_raise(user: User, settings: Settings) -> None:
    redis = get_redis_client()
    rate_limit = settings.speech_rate_limit_per_minute
    if rate_limit > 0:
        allowed = await allow_request_fail_closed(
            redis,
            f"speech_tts_rl:{user.id}",
            limit=rate_limit,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.SPEECH_TTS_RATE_LIMIT_MESSAGE,
            )

    daily_limit = quota_service.speech_tts_limit_for_user(user, settings)
    if not await quota_service.reserve_speech_tts(redis, user.id, limit=daily_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=quota_service.speech_tts_limit_exceeded_message(user),
        )


async def _aiter_nonempty(chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    async for chunk in chunks:
        if chunk:
            yield chunk


_TTS_FOLLOWUP_TTL_SECONDS = 120
# One lead + this many rest clips stay on the same daily TTS slot.
_TTS_FOLLOWUP_MAX_CHUNKS = 32


def _tts_followup_key(user_id: object) -> str:
    return f"speech_tts_followup:{user_id}"


def _normalize_tts_part(raw: str | None) -> str:
    part = (raw or "full").strip().lower()
    if part in {"full", "lead", "rest"}:
        return part
    return "full"


def _reject_oversized_speech_body(content_length: str | None, body_len: int) -> None:
    if content_length is not None:
        try:
            if int(content_length) > SPEECH_MAX_REQUEST_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio payload too large",
                )
        except ValueError:
            pass
    if body_len > SPEECH_MAX_REQUEST_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio payload too large",
        )


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
) -> SpeechTranscriptionOut:
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    text = await speech_service.transcribe_audio(
        settings,
        data,
        filename=filename,
    )
    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not transcribe audio",
        )
    return SpeechTranscriptionOut(text=text)


@router.post("/tts", response_model=SpeechTtsOut)
async def synthesize_speech(
    body: SpeechTtsIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechTtsOut:
    if not settings.speech_tts_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    redis = get_redis_client()
    rate_limit = settings.speech_rate_limit_per_minute
    daily_limit = quota_service.speech_tts_limit_for_user(user, settings)
    part = _normalize_tts_part(body.part)
    reserved_quota = False
    followup_key = _tts_followup_key(user.id)
    followup = await redis.get(followup_key) if part == "rest" else None
    # Same utterance as the lead: more short clips, one daily slot, no per-minute burn.
    billed = not (part == "rest" and followup)
    if billed and rate_limit > 0:
        allowed = await allow_request_fail_closed(
            redis,
            f"speech_tts_rl:{user.id}",
            limit=rate_limit,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.SPEECH_TTS_RATE_LIMIT_MESSAGE,
            )
    if billed:
        if not await quota_service.reserve_speech_tts(redis, user.id, limit=daily_limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.speech_tts_limit_exceeded_message(user),
            )
        reserved_quota = True

    try:
        alias = speech_service.normalize_tts_alias(body.model)
        result = await speech_service.synthesize_speech(
            settings,
            body.text,
            language=body.language,
            model_alias=alias,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not synthesize speech",
            )
        audio_bytes, content_type = result
        if part == "lead":
            await redis.set(
                followup_key,
                str(_TTS_FOLLOWUP_MAX_CHUNKS),
                ex=_TTS_FOLLOWUP_TTL_SECONDS,
            )
        elif part == "rest" and followup:
            try:
                remaining = int(followup)
            except ValueError:
                remaining = 0
            if remaining <= 1:
                await redis.delete(followup_key)
            else:
                await redis.set(
                    followup_key,
                    str(remaining - 1),
                    ex=_TTS_FOLLOWUP_TTL_SECONDS,
                )
        return SpeechTtsOut(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            content_type=content_type,
            model=alias,
        )
    except HTTPException as exc:
        if reserved_quota and exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            await quota_service.refund_speech_tts(redis, user.id)
        raise
    except Exception:
        if reserved_quota:
            await quota_service.refund_speech_tts(redis, user.id)
        raise


@router.post("/tts/stream")
async def stream_speech(
    body: SpeechTtsIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> StreamingResponse:
    if not settings.speech_tts_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    await _reserve_tts_or_raise(user, settings)
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
                )
            ):
                got = True
                yield chunk
        finally:
            if not got:
                await quota_service.refund_speech_tts(redis, user.id)

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
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechTranscriptionOut:
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    # Size first — a 6MB clip used to pass the 7.5MB body cap, reserve quota,
    # then fail as 502 when the service rejected at 5MB.
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        _reject_oversized_speech_body(request.headers.get("content-length"), 0)
        try:
            raw = await request.body()
            _reject_oversized_speech_body(None, len(raw))
            payload = SpeechTranscriptionIn.model_validate(json.loads(raw))
            data = base64.b64decode(payload.audio_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio payload",
            ) from exc
        _reject_oversized_audio(data)
        filename = payload.filename
    else:
        # Multipart: check Content-Length BEFORE request.form() parses the body.
        _reject_oversized_speech_body(request.headers.get("content-length"), 0)
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
    rate_limit = settings.speech_rate_limit_per_minute
    if rate_limit > 0:
        allowed = await allow_request_fail_closed(
            redis,
            f"speech_rl:{user.id}",
            limit=rate_limit,
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

    try:
        return await _transcribe_bytes(settings, data, filename)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            await quota_service.refund_speech_transcription(redis, user.id)
        raise
    except Exception:
        await quota_service.refund_speech_transcription(redis, user.id)
        raise


@router.get("/live", response_model=SpeechLiveStatusOut)
async def live_talk_status(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveStatusOut:
    if not settings.speech_live_talk_enabled:
        return SpeechLiveStatusOut(enabled=False, entitled=False, remaining=0, limit=0)
    try:
        return await _live_talk_status(user, settings)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc


@router.post("/live/turn", response_model=SpeechLiveStatusOut)
async def live_talk_turn(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveStatusOut:
    if not settings.speech_live_talk_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    if not plan_service.is_pro(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=quota_service.LIVE_TALK_REQUIRES_PRO_MESSAGE,
        )

    redis = get_redis_client()
    rate_limit = settings.speech_rate_limit_per_minute
    try:
        if rate_limit > 0:
            allowed = await allow_request_fail_closed(
                redis,
                f"speech_live_rl:{user.id}",
                limit=rate_limit,
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
        return await _live_talk_status(user, settings)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc


@router.post("/live/refund", response_model=SpeechLiveStatusOut)
async def live_talk_refund(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveStatusOut:
    if not settings.speech_live_talk_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    redis = get_redis_client()
    try:
        refunded = await quota_service.refund_live_talk_if_pending(redis, user.id)
        return await _live_talk_status(user, settings, refunded=refunded)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc


@router.post("/live/commit", response_model=SpeechLiveStatusOut)
async def live_talk_commit(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveStatusOut:
    """Lock in the reserved turn so a later refund cannot claw it back."""
    if not settings.speech_live_talk_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    redis = get_redis_client()
    try:
        await quota_service.clear_live_talk_pending(redis, user.id)
        return await _live_talk_status(user, settings)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc


@router.post("/live/speak", response_model=SpeechLiveSpeakOut)
async def live_talk_speak(
    body: SpeechLiveSpeakIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveSpeakOut:
    """Speech-to-speech live talk. Does not use Whisper transcription."""
    if not settings.speech_live_talk_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    if not plan_service.is_pro(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=quota_service.LIVE_TALK_REQUIRES_PRO_MESSAGE,
        )

    try:
        data = base64.b64decode(body.audio_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio payload",
        ) from exc
    _reject_oversized_audio(data)

    redis = get_redis_client()
    rate_limit = settings.speech_rate_limit_per_minute
    reserved = False
    try:
        if rate_limit > 0:
            allowed = await allow_request_fail_closed(
                redis,
                f"speech_live_rl:{user.id}",
                limit=rate_limit,
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
        reserved = True
        result = await speech_service.speech_to_speech(
            settings,
            data,
            filename=body.filename,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not complete live talk",
            )
        audio_bytes, content_type, transcript = result
        await quota_service.clear_live_talk_pending(redis, user.id)
        status_out = await _live_talk_status(user, settings)
        return SpeechLiveSpeakOut(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            content_type=content_type,
            transcript=transcript,
            remaining=status_out.remaining,
            limit=status_out.limit,
        )
    except HTTPException as exc:
        if reserved and exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            await quota_service.refund_live_talk_if_pending(redis, user.id)
        raise
    except RedisUnavailableError as exc:
        if reserved:
            await quota_service.refund_live_talk_if_pending(redis, user.id)
        raise redis_unavailable_http_exception(exc) from exc
    except Exception:
        if reserved:
            await quota_service.refund_live_talk_if_pending(redis, user.id)
        raise
