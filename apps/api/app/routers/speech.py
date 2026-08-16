import base64
import binascii
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import (
    SpeechTranscriptionIn,
    SpeechTranscriptionOut,
    SpeechTtsIn,
    SpeechTtsOut,
)
from app.services import quota as quota_service
from app.services import speech as speech_service

router = APIRouter(prefix="/speech", tags=["speech"])

TTS_STREAM_MEDIA_TYPE = "audio/L16;rate=24000;channels=1"


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


MAX_SPEECH_JSON_BYTES = 7_500_000
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
            if int(content_length) > MAX_SPEECH_JSON_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio payload too large",
                )
        except ValueError:
            pass
    if body_len > MAX_SPEECH_JSON_BYTES:
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
            return await _transcribe_bytes(settings, data, payload.filename)

        # Multipart path: check Content-Length BEFORE request.form() parses
        # the body (form() buffers the whole multipart body into memory/disk).
        # Without this, a client could send a huge multipart body and the
        # server would buffer it all before any size check could reject it.
        _reject_oversized_speech_body(request.headers.get("content-length"), 0)
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing audio file",
            )
        # Secondary guard: the UploadFile's declared .size (from the multipart
        # Content-Disposition) may differ from the top-level Content-Length
        # when there are multiple parts. Check it before reading the bytes.
        declared_size = getattr(upload, "size", None)
        if declared_size is not None:
            _reject_oversized_speech_body(None, int(declared_size))
        data = await upload.read()  # type: ignore[union-attr]
        _reject_oversized_speech_body(None, len(data))
        filename = getattr(upload, "filename", None) or "speech.m4a"
        return await _transcribe_bytes(settings, data, filename)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            await quota_service.refund_speech_transcription(redis, user.id)
        raise
    except Exception:
        await quota_service.refund_speech_transcription(redis, user.id)
        raise
