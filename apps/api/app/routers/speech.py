import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import SpeechTranscriptionIn, SpeechTranscriptionOut
from app.services import quota as quota_service
from app.services import speech as speech_service

router = APIRouter(prefix="/speech", tags=["speech"])


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
        allowed = await allow_request(
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
            try:
                payload = SpeechTranscriptionIn.model_validate(await request.json())
                data = base64.b64decode(payload.audio_base64, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid audio payload",
                ) from exc
            return await _transcribe_bytes(settings, data, payload.filename)

        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing audio file",
            )
        data = await upload.read()  # type: ignore[union-attr]
        filename = getattr(upload, "filename", None) or "speech.m4a"
        return await _transcribe_bytes(settings, data, filename)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            await quota_service.refund_speech_transcription(redis, user.id)
        raise
