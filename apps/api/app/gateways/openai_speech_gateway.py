"""Direct OpenAI Realtime boundary for Live Talk.

Composer STT stays on OpenRouter. Live Talk uses OpenAI Realtime directly.
The permanent OpenAI API key never leaves the Recall server; mobile receives
only a short-lived Realtime client secret and performs the SDP exchange itself.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
_OPENAI_REALTIME_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"
_REALTIME_TIMEOUT_SECONDS = 10.0
_REALTIME_CONNECT_RETRIES = 2
_DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1"
_REALTIME_INPUT_TRANSCRIBE_MODEL = "gpt-transcribe"


@dataclass(frozen=True, slots=True)
class RealtimeCallResult:
    answer_sdp: str
    call_id: str | None


@dataclass(frozen=True, slots=True)
class RealtimeClientSecretResult:
    value: str
    expires_at: int


def realtime_model(settings: Settings) -> str:
    return settings.openai_realtime_model.strip() or _DEFAULT_REALTIME_MODEL


def realtime_configured(settings: Settings) -> bool:
    return bool(settings.openai_api_key.strip()) and settings.speech_realtime_voice_enabled


def realtime_session_config(settings: Settings, instructions: str) -> dict[str, object]:
    return {
        "type": "realtime",
        "model": realtime_model(settings),
        "output_modalities": ["audio"],
        "instructions": instructions,
        # Input transcription is our authorization boundary for a spoken turn.
        # Ask OpenAI for confidence data when available so mobile can diagnose
        # low-confidence / phantom turns without putting them in Recall history.
        "include": ["item.input_audio_transcription.logprobs"],
        "audio": {
            "input": {
                "noise_reduction": {"type": "near_field"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.72,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 600,
                    # Critical: VAD detects and commits turns, but it must never
                    # create or interrupt a response by itself. Mobile validates
                    # the committed transcript first, deletes echo/phantom items,
                    # and sends response.create only for an accepted user turn.
                    "create_response": False,
                    "interrupt_response": False,
                },
                "transcription": {
                    "model": _REALTIME_INPUT_TRANSCRIBE_MODEL,
                    "prompt": (
                        "Transcribe only words actually spoken by the user. "
                        "Do not invent speech from silence, background noise, "
                        "music, or assistant speaker playback."
                    ),
                },
            },
            "output": {"voice": "marin"},
        },
    }


async def create_realtime_client_secret(
    settings: Settings,
    *,
    instructions: str,
    safety_identifier: str,
) -> RealtimeClientSecretResult | None:
    """Mint a short-lived key that mobile can use for direct WebRTC setup."""
    key = settings.openai_api_key.strip()
    if not key or not settings.speech_realtime_voice_enabled:
        return None

    model = realtime_model(settings)
    client = get_pooled_client(
        _REALTIME_TIMEOUT_SECONDS,
        connect_retries=_REALTIME_CONNECT_RETRIES,
    )
    try:
        response = await client.post(
            _OPENAI_REALTIME_CLIENT_SECRETS_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "OpenAI-Safety-Identifier": safety_identifier[:128],
            },
            json={"session": realtime_session_config(settings, instructions)},
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenAI Realtime client-secret failed model=%s status=%s body=%s",
                model,
                response.status_code,
                response.text[:800],
            )
        response.raise_for_status()
        payload = response.json()
        value = str(payload.get("value") or "").strip()
        expires_at = int(payload.get("expires_at") or 0)
        if not value:
            logger.warning("OpenAI Realtime client-secret response missing value")
            return None
        return RealtimeClientSecretResult(value=value, expires_at=expires_at)
    except Exception:
        logger.exception("Could not mint OpenAI Realtime client secret")
        return None


async def create_realtime_call(
    settings: Settings,
    *,
    offer_sdp: str,
    instructions: str,
    safety_identifier: str,
) -> RealtimeCallResult | None:
    """Legacy server-proxied SDP exchange kept temporarily for rollback."""
    key = settings.openai_api_key.strip()
    if not key or not settings.speech_realtime_voice_enabled:
        return None

    model = realtime_model(settings)
    client = get_pooled_client(
        _REALTIME_TIMEOUT_SECONDS,
        connect_retries=_REALTIME_CONNECT_RETRIES,
    )
    try:
        response = await client.post(
            _OPENAI_REALTIME_CALLS_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "OpenAI-Safety-Identifier": safety_identifier[:128],
            },
            files={
                "sdp": (None, offer_sdp, "application/sdp"),
                "session": (
                    None,
                    json.dumps(realtime_session_config(settings, instructions)),
                    "application/json",
                ),
            },
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenAI Realtime call failed model=%s status=%s body=%s",
                model,
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
