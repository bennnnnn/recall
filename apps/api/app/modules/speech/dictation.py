"""Live dictation: the composer mic's OpenAI transcription session, which the server owns.

The recorded dictation waited for the whole clip: the phone recorded, uploaded it when
the user stopped, and the words came back only then. Now the phone streams the mic to an
OpenAI Realtime transcription session over WebRTC, as live talk does, and the words land
in the composer as they are spoken. No model answers in that session; it only transcribes.

As with live talk, the client secret never leaves the server. A mint (``open_session``)
takes one of the day's ``speech_transcription`` slots and keeps the secret; the phone's
offer comes here (``connect``), which opens the call, keeps its id and schedules its
hang-up for ``speech_dictation_max_seconds`` later, so a mic left open cannot run up
cost. The phone's stop (``end``) hangs the call up at once, and gives the slot back when
nothing was heard. That last part is the phone's word, so it is honoured only
``EMPTY_REFUNDS_PER_DAY`` times a day.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import status
from redis.asyncio import Redis

from app.core import jobs
from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import openai_speech_gateway
from app.models.model_catalog import openrouter_slug
from app.modules.speech import live_call
from app.modules.speech.gates import SpeechRefusedError
from app.services import quota as quota_service
from app.services.quota import counters

logger = logging.getLogger(__name__)

HANGUP_JOB = "dictation_hangup"
_DICTATION_ALIAS = "speech-dictation-model"
# The phone connects right after the mint; an unused secret is dropped after this.
_SECRET_TTL_SECONDS = 60
# The hang-up comes this long after the call opens plus the take's own limit: the phone's
# timer starts only once its data channel is up (up to 10 s), then the stop's tail and the
# wait for the last words' text (about 3 s).
_HANGUP_GRACE_SECONDS = 15
# A held call id or slot outlives the hang-up by every retry its job can make.
_TAIL_SECONDS = 15 * 60
# Refunds a day for a take the phone says heard nothing: an honest phone needs a few (a
# tap by mistake, a noisy room); a modified one cannot turn the day's cap off with it.
EMPTY_REFUNDS_PER_DAY = 10


class DictationUnconfirmedError(Exception):
    """OpenAI did not confirm the hang-up; the job retries (``core/jobs`` backoff)."""


@dataclass(frozen=True, slots=True)
class DictationSession:
    session_id: str
    expires_at: int
    model: str
    max_duration_seconds: int


def dictation_model(settings: Settings) -> str:
    """The operator's override when it can stream, else the catalog's dictation model."""
    override = settings.speech_dictation_model.strip()
    if override and openai_speech_gateway.can_stream_transcribe_with(override):
        return override.removeprefix("openai/")
    return openrouter_slug(_DICTATION_ALIAS).removeprefix("openai/")


def _secret_key(user_id: UUID, session_id: str) -> str:
    return f"dictation_secret:{user_id}:{session_id}"


def _call_key(user_id: UUID, session_id: str) -> str:
    return f"dictation_call:{user_id}:{session_id}"


def _slot_key(user_id: UUID, session_id: str) -> str:
    return f"dictation_slot:{user_id}:{session_id}"


def _refunds_key(user_id: UUID, day: date) -> str:
    return f"dictation_empty_refunds:{user_id}:{day.isoformat()}"


def _text(raw: Any) -> str:
    return raw.decode() if isinstance(raw, bytes | bytearray) else str(raw)


def _hold_seconds(settings: Settings) -> int:
    hang_up = settings.speech_dictation_max_seconds + _HANGUP_GRACE_SECONDS
    return int(hang_up + jobs.retry_span_s() + _TAIL_SECONDS) + 1


def _ended() -> SpeechRefusedError:
    return SpeechRefusedError(
        "Voice input session is not active",
        status_code=status.HTTP_403_FORBIDDEN,
        code="dictation_session_ended",
    )


def _failed(status_code: int = status.HTTP_502_BAD_GATEWAY) -> SpeechRefusedError:
    return SpeechRefusedError("Could not start voice input", status_code=status_code)


async def open_session(
    redis: Redis,
    settings: Settings,
    user_id: UUID,
    *,
    day: date,
    language: str | None,
) -> DictationSession:
    """Mint the session's secret and keep it, with the slot ``day`` it was charged to.

    The caller has passed the gates and reserved the slot, and gives it back when this
    raises (no session was opened)."""
    model = dictation_model(settings)
    result = await openai_speech_gateway.create_transcription_client_secret(
        settings,
        model=model,
        language=language,
        safety_identifier=openai_speech_gateway.safety_identifier(user_id),
    )
    if result is None:
        raise _failed()
    session_id = secrets.token_urlsafe(16)
    await redis.set(_slot_key(user_id, session_id), day.isoformat(), ex=_hold_seconds(settings))
    await redis.set(_secret_key(user_id, session_id), result.value, ex=_SECRET_TTL_SECONDS)
    return DictationSession(
        session_id=session_id,
        expires_at=result.expires_at,
        model=model,
        max_duration_seconds=settings.speech_dictation_max_seconds,
    )


async def connect(
    redis: Redis, settings: Settings, user_id: UUID, session_id: str, offer_sdp: str
) -> str:
    """Open the session's OpenAI call with the phone's offer; returns OpenAI's answer.

    Once per session: the secret is taken as it is used. The call's hang-up is scheduled
    for the take's limit. A connect that opens no usable call gives the slot back (no
    audio reached OpenAI), so the phone's recorded fallback is charged only once.
    """
    session_id = session_id.strip()
    raw_secret = await redis.getdel(_secret_key(user_id, session_id))
    if raw_secret is None:
        raise _ended()
    call = await openai_speech_gateway.create_realtime_call(
        settings, client_secret=_text(raw_secret), offer_sdp=offer_sdp
    )
    if call is None:
        await _give_slot_back(redis, user_id, session_id)
        raise _failed()
    await redis.set(_call_key(user_id, session_id), call.call_id, ex=_hold_seconds(settings))
    try:
        # Raises, unlike ``enqueue_later``: without this job nothing ends a forgotten mic.
        await jobs.schedule_job(
            redis,
            HANGUP_JOB,
            _hangup_payload(user_id, session_id),
            delay_s=settings.speech_dictation_max_seconds + _HANGUP_GRACE_SECONDS,
        )
    except Exception:
        logger.exception("dictation_hangup could not be scheduled; ending the call")
        if await openai_speech_gateway.hangup_realtime_call(settings, call.call_id) == "failed":
            logger.error("dictation call=%s could not be hung up", call.call_id)
        # No take ran: the voice input goes back (best-effort, Redis may be what failed).
        try:
            await _give_slot_back(redis, user_id, session_id)
        except Exception:
            logger.warning("dictation slot not given back after a scheduling failure")
        raise _failed(status.HTTP_503_SERVICE_UNAVAILABLE) from None
    if "v=0" not in call.answer_sdp:
        await end(redis, settings, user_id, session_id, heard=False, refund_capped=False)
        raise _failed()
    await quota_service.record_voice_spend(redis, quota_service.STT_SPEND_USD)
    return call.answer_sdp


async def end(
    redis: Redis,
    settings: Settings,
    user_id: UUID,
    session_id: str,
    *,
    heard: bool,
    refund_capped: bool = True,
) -> None:
    """The phone stopped: hang the call up now, and give the slot back when nothing was
    heard. Idempotent. A hang-up OpenAI does not confirm is left to the job, which tries
    again."""
    session_id = session_id.strip()
    if not await _hang_up(redis, settings, user_id, session_id):
        await jobs.enqueue_later(redis, HANGUP_JOB, _hangup_payload(user_id, session_id), delay_s=0)
    if not heard:
        await _give_slot_back(redis, user_id, session_id, capped=refund_capped)


async def _hang_up(redis: Redis, settings: Settings, user_id: UUID, session_id: str) -> bool:
    return await live_call.hang_up_kept_call(
        redis,
        settings,
        secret_key=_secret_key(user_id, session_id),
        call_key=_call_key(user_id, session_id),
    )


async def _give_slot_back(
    redis: Redis, user_id: UUID, session_id: str, *, capped: bool = False
) -> None:
    """Refund the session's slot, once. ``capped``: only so many times a day."""
    raw = await redis.getdel(_slot_key(user_id, session_id))
    if raw is None:
        return
    day = date.fromisoformat(_text(raw))
    if capped:
        key = _refunds_key(user_id, counters.utc_today())
        refunds = await redis.incr(key)
        if refunds == 1:
            await redis.expire(key, int(timedelta(days=2).total_seconds()))
        if refunds > EMPTY_REFUNDS_PER_DAY:
            return
    await counters.refund("speech_transcription", redis, user_id, day=day)


def _hangup_payload(user_id: UUID, session_id: str) -> dict[str, object]:
    return {"user_id": str(user_id), "session_id": session_id}


async def handle_hangup_job(settings: Settings, payload: dict[str, Any]) -> None:
    """``dictation_hangup``: at the take's limit, or after the phone's stop could not
    confirm a hang-up. Raises while OpenAI does not confirm, so the queue retries."""
    try:
        user_id = UUID(str(payload.get("user_id")))
    except ValueError:
        logger.warning("dictation_hangup invalid user_id=%r", payload.get("user_id"))
        return
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return
    if not await _hang_up(get_redis_client(), settings, user_id, session_id):
        raise DictationUnconfirmedError(session_id)
