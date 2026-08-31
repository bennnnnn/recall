import asyncio
import base64
import binascii
import hashlib
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.deps import get_current_user, get_settings_dep, redis_unavailable_http_exception
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.exceptions import RedisUnavailableError
from app.models.orm import Message, User
from app.models.schemas import (
    SpeechLiveSpeakIn,
    SpeechLiveStatusOut,
    SpeechTranscriptionIn,
    SpeechTranscriptionOut,
    SpeechTtsIn,
    SpeechTtsOut,
)
from app.models.schemas.integrations import SPEECH_MAX_AUDIO_BYTES, SPEECH_MAX_REQUEST_BYTES
from app.services import live_talk as live_talk_service
from app.services import plan as plan_service
from app.services import quota as quota_service
from app.services import speech as speech_service
from app.services.live_talk_stream import (
    LIVE_TALK_EMPTY_TRANSCRIPT,
    LiveTalkStreamEvent,
    iter_speech_to_speech,
)

router = APIRouter(prefix="/speech", tags=["speech"])
logger = logging.getLogger(__name__)

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


def _raise_live_talk_route_gone(settings: Settings) -> None:
    if not settings.speech_live_talk_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Live talk reserves on POST /speech/live/speak",
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
# Lead + rest share one billed slot; cap unbilled rest text at one TTS request.
_TTS_FOLLOWUP_MAX_CHARS = 4000
_CONSUME_TTS_FOLLOWUP_LUA = """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
local clips, chars, stored_hash
local first = string.find(raw, ':')
if not first then
  clips = tonumber(raw) or 0
  chars = tonumber(ARGV[3]) or 0
  stored_hash = ''
else
  local second = string.find(raw, ':', first + 1)
  clips = tonumber(string.sub(raw, 1, first - 1)) or 0
  if second then
    chars = tonumber(string.sub(raw, first + 1, second - 1)) or 0
    stored_hash = string.sub(raw, second + 1)
  else
    chars = tonumber(string.sub(raw, first + 1)) or 0
    stored_hash = ''
  end
end
local want_hash = ARGV[4] or ''
if stored_hash == '' or want_hash == '' or stored_hash ~= want_hash then
  return 0
end
local need = tonumber(ARGV[1]) or 0
local ttl = tonumber(ARGV[2]) or 0
if clips < 1 or chars < need then
  return 0
end
clips = clips - 1
chars = chars - need
if clips < 1 or chars < 1 then
  redis.call('DEL', KEYS[1])
else
  redis.call('SET', KEYS[1], clips .. ':' .. chars .. ':' .. stored_hash, 'EX', ttl)
end
return 1
"""


def _tts_followup_key(user_id: object) -> str:
    return f"speech_tts_followup:{user_id}"


def _tts_lead_hash(lead_text: str) -> str:
    return hashlib.sha256(lead_text.encode("utf-8")).hexdigest()[:16]


def _normalize_tts_part(raw: str | None) -> str:
    part = (raw or "full").strip().lower()
    if part in {"full", "lead", "rest"}:
        return part
    return "full"


def _tts_followup_payload(lead_text: str) -> str | None:
    remaining_chars = _TTS_FOLLOWUP_MAX_CHARS - len(lead_text)
    if remaining_chars <= 0:
        return None
    return f"{_TTS_FOLLOWUP_MAX_CHUNKS}:{remaining_chars}:{_tts_lead_hash(lead_text)}"


def _parse_tts_followup(raw: object) -> tuple[int, int, str] | None:
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes | bytearray) else str(raw)
    parts = text.split(":", 2)
    try:
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), parts[2]
        if len(parts) == 2:
            return int(parts[0]), int(parts[1]), ""
        return int(text), _TTS_FOLLOWUP_MAX_CHARS, ""
    except ValueError:
        return None


async def _try_consume_tts_followup_plain(
    redis: Redis, key: str, char_count: int, lead_hash: str
) -> bool:
    parsed = _parse_tts_followup(await redis.get(key))
    if parsed is None:
        return False
    clips, chars, stored_hash = parsed
    if not stored_hash or stored_hash != lead_hash:
        return False
    if clips < 1 or chars < char_count:
        return False
    clips -= 1
    chars -= char_count
    if clips < 1 or chars < 1:
        await redis.delete(key)
    else:
        await redis.set(
            key,
            f"{clips}:{chars}:{stored_hash}",
            ex=_TTS_FOLLOWUP_TTL_SECONDS,
        )
    return True


async def _try_consume_tts_followup(
    redis: Redis, key: str, char_count: int, lead_hash: str
) -> bool:
    try:
        result = await redis.eval(
            _CONSUME_TTS_FOLLOWUP_LUA,
            1,
            key,
            char_count,
            _TTS_FOLLOWUP_TTL_SECONDS,
            _TTS_FOLLOWUP_MAX_CHARS,
            lead_hash,
        )
        return int(result) == 1
    except ResponseError:
        return await _try_consume_tts_followup_plain(redis, key, char_count, lead_hash)


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
    if text is None:
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
    consumed_followup = False
    lead_hash = (body.lead_hash or "").strip()
    if part == "rest":
        consumed_followup = await _try_consume_tts_followup(
            redis, followup_key, len(body.text), lead_hash
        )
    # Same utterance as the lead: short clips within the char budget share one slot.
    billed = not consumed_followup
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
            payload = _tts_followup_payload(body.text)
            if payload is not None:
                await redis.set(
                    followup_key,
                    payload,
                    ex=_TTS_FOLLOWUP_TTL_SECONDS,
                )
        return SpeechTtsOut(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            content_type=content_type,
            model=alias,
            lead_hash=_tts_lead_hash(body.text) if part == "lead" else None,
        )
    except HTTPException as exc:
        if reserved_quota and exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            await quota_service.refund_speech_tts(redis, user.id)
        raise
    except asyncio.CancelledError:
        if reserved_quota:
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


@router.post("/live/turn")
async def live_talk_turn(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Gone — speak self-reserves. Stale clients get 410 instead of a second slot."""
    _raise_live_talk_route_gone(settings)


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


@router.post("/live/commit")
async def live_talk_commit(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Gone — speak clears pending after audio; refund stays for abort-before-clip."""
    _raise_live_talk_route_gone(settings)


def _sse_data(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _live_talk_event_sse(event: LiveTalkStreamEvent) -> str:
    if event.kind == "audio":
        return _sse_data(
            {
                "type": "audio",
                "audio_base64": base64.b64encode(event.audio_wav).decode("ascii"),
                "content_type": "audio/wav",
            }
        )
    if event.kind == "error":
        return _sse_data(
            {
                "type": "error",
                "detail": event.text or "Could not complete live talk",
            }
        )
    return _sse_data({"type": event.kind, "text": event.text})


@router.post("/live/speak")
async def live_talk_speak(
    body: SpeechLiveSpeakIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> StreamingResponse:
    """Speech-to-speech live talk. Streams WAV clips; persists transcripts as chat."""
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

    history: list[tuple[str, str]] | None = None
    untitled = False
    chat_id = body.chat_id
    if chat_id is not None:
        async with SessionLocal() as session:
            loaded = await live_talk_service.load_live_talk_history(
                session, chat_id=chat_id, user_id=user.id
            )
        if loaded is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        history, untitled = loaded

    redis = get_redis_client()
    rate_limit = settings.speech_rate_limit_per_minute
    reserved = False
    if rate_limit > 0:
        try:
            allowed = await allow_request_fail_closed(
                redis,
                f"speech_live_rl:{user.id}",
                limit=rate_limit,
                window_seconds=60,
            )
        except RedisUnavailableError as exc:
            raise redis_unavailable_http_exception(exc) from exc
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.LIVE_TALK_RATE_LIMIT_MESSAGE,
            )
    daily_limit = quota_service.live_talk_limit_for_user(user, settings)
    try:
        if not await quota_service.reserve_live_talk(redis, user.id, limit=daily_limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.live_talk_limit_exceeded_message(user),
            )
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    reserved = True

    async def body_iter() -> AsyncIterator[str]:
        got_audio = False
        user_text = ""
        assistant_text = ""
        user_written = False
        assistant_written = False
        user_msg: Message | None = None
        asst_msg: Message | None = None

        async def persist_user_now() -> None:
            nonlocal user_written, user_msg
            if user_written or chat_id is None or not user_text:
                return
            row, _ = await live_talk_service.persist_live_talk_turn(
                user=user,
                chat_id=chat_id,
                user_text=user_text,
                assistant_text="",
                untitled=False,
                settings=settings,
                redis=redis,
                write_assistant=False,
                enqueue_jobs=False,
            )
            user_written = True
            user_msg = row

        async def persist_if_needed() -> tuple[Message | None, Message | None]:
            nonlocal assistant_written, asst_msg
            if chat_id is None:
                return user_msg, asst_msg
            await persist_user_now()
            if assistant_text and not assistant_written:
                assistant_written = True
                _, asst_msg = await live_talk_service.persist_live_talk_turn(
                    user=user,
                    chat_id=chat_id,
                    user_text=user_text,
                    assistant_text=assistant_text,
                    untitled=untitled,
                    settings=settings,
                    redis=redis,
                    write_user=False,
                    enqueue_jobs=True,
                )
            elif user_written and not assistant_written:
                assistant_written = True
                await live_talk_service.persist_live_talk_turn(
                    user=user,
                    chat_id=chat_id,
                    user_text=user_text,
                    assistant_text=assistant_text,
                    untitled=untitled,
                    settings=settings,
                    redis=redis,
                    write_user=False,
                    write_assistant=False,
                    enqueue_jobs=True,
                )
            return user_msg, asst_msg

        try:
            async for event in iter_speech_to_speech(
                settings,
                data,
                filename=body.filename,
                history=history,
            ):
                if event.kind == "error":
                    yield _live_talk_event_sse(event)
                    return
                if event.kind == "audio":
                    got_audio = True
                elif event.kind == "user":
                    user_text = event.text
                elif event.kind == "assistant":
                    assistant_text = event.text
                yield _live_talk_event_sse(event)
                if event.kind == "user":
                    await persist_user_now()
            if not got_audio:
                detail = (
                    LIVE_TALK_EMPTY_TRANSCRIPT if not user_text else "Could not complete live talk"
                )
                yield _sse_data({"type": "error", "detail": detail})
                return
            user_msg, asst_msg = await persist_if_needed()
            status_out = await _live_talk_status(user, settings)
            yield _sse_data(
                {
                    "type": "done",
                    "remaining": status_out.remaining,
                    "limit": status_out.limit,
                    "user_message": live_talk_service.message_out_payload(user_msg),
                    "assistant_message": live_talk_service.message_out_payload(asst_msg),
                }
            )
        except Exception:
            if got_audio:
                logger.exception("Live talk stream error after audio")
            raise
        finally:
            try:
                await live_talk_service.settle_live_talk_after_stream(
                    got_audio=got_audio,
                    reserved=reserved,
                    redis=redis,
                    user_id=user.id,
                    persist=persist_if_needed,
                )
            except Exception:
                logger.exception("Live talk settle after stream failed")

    return StreamingResponse(
        body_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
