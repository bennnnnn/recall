"""Direct OpenAI speech boundary for low-latency STT and Realtime voice.

Normal chat continues to use OpenRouter. Speech is intentionally direct so
voice latency is not coupled to an extra routing hop.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
_OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
_TRANSCRIBE_TIMEOUT_SECONDS = 20.0
_REALTIME_TIMEOUT_SECONDS = 15.0
_DEFAULT_STT_MODEL = "gpt-transcribe"
_DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1"


@dataclass(frozen=True, slots=True)
class RealtimeCallResult:
    answer_sdp: str
    call_id: str | None


def api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def stt_model() -> str:
    return os.getenv("OPENAI_STT_MODEL", _DEFAULT_STT_MODEL).strip() or _DEFAULT_STT_MODEL


def realtime_model() -> str:
    return (
        os.getenv("OPENAI_REALTIME_MODEL", _DEFAULT_REALTIME_MODEL).strip()
        or _DEFAULT_REALTIME_MODEL
    )


def realtime_enabled() -> bool:
    raw = os.getenv("RECALL_REALTIME_VOICE_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def transcribe(
    audio_bytes: bytes,
    *,
    filename: str,
    language: str | None = None,
    prompt: str | None = None,
) -> str | None:
    """Transcribe one completed recording directly with OpenAI."""
    key = api_key()
    if not key:
        return None

    data: dict[str, str] = {"model": stt_model()}
    lang = (language or "").strip()
    if lang:
        data["language"] = lang
    context = (prompt or "").strip()
    if context:
        data["prompt"] = context[:1000]

    client = get_pooled_client(_TRANSCRIBE_TIMEOUT_SECONDS)
    try:
        response = await client.post(
            _OPENAI_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {key}"},
            data=data,
            files={"file": (filename or "speech.m4a", audio_bytes)},
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenAI transcription failed model=%s status=%s body=%s",
                data["model"],
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("text") or "").strip()
    except Exception:
        logger.exception(
            "Direct OpenAI transcription failed model=%s bytes=%s",
            data["model"],
            len(audio_bytes),
        )
        return None


async def create_realtime_call(
    *,
    offer_sdp: str,
    instructions: str,
    safety_identifier: str,
) -> RealtimeCallResult | None:
    """Exchange a mobile WebRTC SDP offer for OpenAI's SDP answer.

    The permanent API key remains server-side; the mobile app never receives it.
    """
    key = api_key()
    if not key or not realtime_enabled():
        return None

    session = {
        "type": "realtime",
        "model": realtime_model(),
        "output_modalities": ["audio"],
        "instructions": instructions,
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "semantic_vad",
                    "create_response": True,
                    "interrupt_response": True,
                },
                "transcription": {"model": stt_model()},
            },
            "output": {"voice": "marin"},
        },
    }

    client = get_pooled_client(_REALTIME_TIMEOUT_SECONDS)
    try:
        response = await client.post(
            _OPENAI_REALTIME_CALLS_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "OpenAI-Safety-Identifier": safety_identifier[:128],
            },
            files={
                "sdp": (None, offer_sdp, "application/sdp"),
                "session": (None, json.dumps(session), "application/json"),
            },
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenAI Realtime call failed model=%s status=%s body=%s",
                realtime_model(),
                response.status_code,
                response.text[:800],
            )
        response.raise_for_status()
        return RealtimeCallResult(
            answer_sdp=response.text,
            call_id=response.headers.get("location"),
        )
    except Exception:
        logger.exception("Could not create OpenAI Realtime WebRTC call")
        return None
