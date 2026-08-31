"""Direct OpenAI Realtime WebRTC boundary.

Composer STT stays on OpenRouter (`openai/gpt-transcribe`). Live Talk cannot:
OpenRouter has no Realtime/WebRTC API, so the SDP exchange is OpenAI-direct.
The permanent API key never leaves this server.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
_REALTIME_TIMEOUT_SECONDS = 15.0
_DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1"
_REALTIME_INPUT_TRANSCRIBE_MODEL = "gpt-transcribe"


@dataclass(frozen=True, slots=True)
class RealtimeCallResult:
    answer_sdp: str
    call_id: str | None


def realtime_model(settings: Settings) -> str:
    return settings.openai_realtime_model.strip() or _DEFAULT_REALTIME_MODEL


def realtime_configured(settings: Settings) -> bool:
    return bool(settings.openai_api_key.strip()) and settings.speech_realtime_voice_enabled


async def create_realtime_call(
    settings: Settings,
    *,
    offer_sdp: str,
    instructions: str,
    safety_identifier: str,
) -> RealtimeCallResult | None:
    """Exchange a mobile WebRTC SDP offer for OpenAI's SDP answer."""
    key = settings.openai_api_key.strip()
    if not key or not settings.speech_realtime_voice_enabled:
        return None

    model = realtime_model(settings)
    session = {
        "type": "realtime",
        "model": model,
        "output_modalities": ["audio"],
        "instructions": instructions,
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "semantic_vad",
                    "create_response": True,
                    "interrupt_response": True,
                },
                "transcription": {"model": _REALTIME_INPUT_TRANSCRIBE_MODEL},
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
