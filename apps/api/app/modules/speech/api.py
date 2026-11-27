import base64
import binascii
import json
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings
from app.core.consent import get_consented_user
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.core.request_limits import reject_oversized
from app.core.validation import normalize_locale_code
from app.models.orm import User
from app.modules.billing.entitlements import Feature
from app.modules.speech import live_talk as live_talk_service
from app.modules.speech import service as speech_service
from app.modules.speech import voice_preview
from app.modules.speech.gates import (
    charge_tts_tokens,
    refund_day_on_failure,
    require_plan_feature,
    require_speech_rate,
    require_voice_spend_ok,
    reserve_day_or_raise,
)
from app.modules.speech.listen_reply import remember_reply_language, reply_language
from app.modules.speech.schemas import (
    SPEECH_MAX_AUDIO_BYTES,
    SPEECH_MAX_REQUEST_BYTES,
    SpeechLiveStatusOut,
    SpeechTranscriptionIn,
    SpeechTranscriptionOut,
    SpeechTtsIn,
    SpeechTtsOut,
    VoicePreviewIn,
    VoicePreviewOut,
)
from app.modules.speech.text_language import UNSURE
from app.modules.speech.tts_followup import (
    normalize_tts_part,
    store_tts_followup,
    try_consume_tts_followup,
    tts_followup_key,
    tts_lead_hash,
)
from app.services import quota as quota_service

router = APIRouter(prefix="/speech", tags=["speech"])


def _reject_oversized_audio(data: bytes) -> None:
    if len(data) > SPEECH_MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Audio payload too large",
        )


async def _transcribe_bytes(
    settings: Settings,
    data: bytes,
    filename: str,
    language: str | None = None,
    on_call: Callable[[], None] | None = None,
    on_spend: Callable[[float], None] | None = None,
) -> SpeechTranscriptionOut:
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    text = await speech_service.transcribe_audio(
        settings, data, filename=filename, language=language, on_call=on_call, on_spend=on_spend
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
    followup_key = tts_followup_key(user.id)
    consumed_followup = False
    lead_hash = (body.lead_hash or "").strip()
    if part == "rest":
        consumed_followup = await try_consume_tts_followup(
            redis, followup_key, len(body.text), lead_hash
        )
    # Same utterance as the lead: its rest shares the lead's request (rate, spend).
    billed = not consumed_followup
    if billed:
        await require_speech_rate(
            redis,
            settings,
            f"speech_tts_rl:{user.id}",
            quota_service.SPEECH_TTS_RATE_LIMIT_MESSAGE,
        )
    # No daily count: every part is charged to the day's token budget by its length.
    charged = await charge_tts_tokens(redis, user, settings, body.text)

    # A rest clip plays in its reply's language unless it says otherwise (``listen_reply``).
    lead_language = await reply_language(redis, user.id, lead_hash) if part == "rest" else None
    played: list[speech_service.ListenClip] = []
    async with charged as refund:
        alias = speech_service.normalize_tts_alias(body.model)
        result = await speech_service.synthesize_speech(
            settings,
            body.text,
            language=body.language,
            model_alias=alias,
            reply_voice=user.reply_voice,
            reply_language=lead_language,
            on_call=refund.spend,
            on_played=played.append,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not synthesize speech",
            )
        audio_bytes, content_type = result
        if part == "lead":
            await store_tts_followup(redis, followup_key, body.text)
        # Every clip is paid for by its characters, a rest clip that took no daily slot too.
        for clip in played:
            # What played, not what was read: a lead tts-1 played keeps the reply on it, and
            # so does a rest clip Kokoro failed on, so the reply's voice does not come back.
            if part == "lead":
                await remember_reply_language(
                    redis, user.id, tts_lead_hash(body.text), clip.reply_language
                )
            elif part == "rest" and clip.fell_back:
                await remember_reply_language(redis, user.id, lead_hash, UNSURE)
            await quota_service.record_voice_spend(redis, clip.usd)
        return SpeechTtsOut(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            content_type=content_type,
            model=alias,
            lead_hash=tts_lead_hash(body.text) if part == "lead" else None,
        )


@router.post("/voice-preview", response_model=VoicePreviewOut)
async def preview_voice(
    body: VoicePreviewIn,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> VoicePreviewOut:
    """The voice picked in Settings saying its name (``voice_preview``). No Listen tokens;
    a per-minute rate limit, and a made clip counts toward the day's provider spend."""
    feature: Feature = "speech_tts" if body.kind == "reply" else "live_talk"
    require_plan_feature(user, settings, feature, quota_service.SPEECH_TTS_NOT_IN_PLAN_MESSAGE)
    redis = get_redis_client()
    await require_voice_spend_ok(redis, settings)
    await require_speech_rate(
        redis,
        settings,
        f"speech_preview_rl:{user.id}",
        quota_service.SPEECH_TTS_RATE_LIMIT_MESSAGE,
    )
    spent: list[float] = []
    try:
        clip = await voice_preview.voice_preview(
            settings,
            redis,
            kind=body.kind,
            voice=body.voice,
            language=normalize_locale_code(user.locale),
            on_spend=spent.append,
        )
    except voice_preview.UnknownVoiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown voice"
        ) from exc
    for usd in spent:
        await quota_service.record_voice_spend(redis, usd)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No preview")
    audio, content_type = clip
    return VoicePreviewOut(
        audio_base64=base64.b64encode(audio).decode("ascii"), content_type=content_type
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Missing audio file",
            )
        declared_size = getattr(upload, "size", None)
        if declared_size is not None and int(declared_size) > SPEECH_MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Audio payload too large",
            )
        data = await upload.read()
        _reject_oversized_audio(data)
        filename = getattr(upload, "filename", None) or "speech.m4a"

    redis = get_redis_client()
    await require_voice_spend_ok(redis, settings)
    await require_speech_rate(
        redis, settings, f"speech_rl:{user.id}", quota_service.SPEECH_RATE_LIMIT_MESSAGE
    )
    day = await reserve_day_or_raise("speech_transcription", redis, user, settings)

    # Once the audio is sent the provider may bill it, so a 502 or a hang-up after
    # that keeps the slot; only a failure before the call gives it back.
    # Each transcriber asked adds its estimate: a Whisper failure retried on OpenAI is both.
    spent: list[float] = []
    # Recorded whatever the outcome: a 502 after both failed, or a hang-up, may still be billed.
    async with refund_day_on_failure("speech_transcription", redis, user.id, day) as refund:
        try:
            return await _transcribe_bytes(
                settings, data, filename, language, refund.spend, spent.append
            )
        finally:
            if spent:
                await quota_service.record_voice_spend(redis, sum(spent))


@router.get("/live", response_model=SpeechLiveStatusOut)
async def live_talk_status(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechLiveStatusOut:
    if not settings.speech_live_talk_enabled:
        return SpeechLiveStatusOut(enabled=False, entitled=False, remaining=0, limit=0)
    return await live_talk_service.live_talk_status(get_redis_client(), user, settings)
