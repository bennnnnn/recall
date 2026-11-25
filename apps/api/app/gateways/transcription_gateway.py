"""OpenRouter speech-to-text HTTP call (provider boundary): the recorded clip's transcript.

``POST /api/v1/audio/transcriptions`` takes the clip as base64 JSON (``input_audio``) and
answers ``{"text", "usage": {"seconds", "cost"}}``. Live dictation is not here: it streams to
OpenAI over WebRTC (``openai_speech_gateway``).
"""

from __future__ import annotations

import base64
import logging

from app.core.config import Settings
from app.core.log_text import log_safe
from app.gateways.http_client import get_pooled_client
from app.gateways.speech_gateway import audio_format_from_filename, stt_language_code

logger = logging.getLogger(__name__)

_OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
# The pooled client's own limit; ``speech.service`` holds each try to far less (its route
# deadline), so a hanging host still leaves the OpenAI fallback time before the phone gives up.
_TRANSCRIBE_TIMEOUT = 30.0
# The Whisper models OpenRouter lists for /audio/transcriptions: the only models an
# operator override may name (``speech.service.resolve_stt_model``).
_WHISPER_MODELS = frozenset(
    {"openai/whisper-large-v3-turbo", "openai/whisper-large-v3", "openai/whisper-1"}
)


def can_transcribe_with(model: str) -> bool:
    """Whether ``model`` is one of OpenRouter's Whisper models this gateway sends."""
    return model.strip() in _WHISPER_MODELS


def _payload(
    model: str, audio_bytes: bytes, audio_format: str, code: str | None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "format": audio_format,
        },
    }
    if code:
        payload["language"] = code
    return payload


async def transcribe_via_openrouter(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
    language: str | None = None,
) -> str | None:
    """The clip's transcript ("" for silence), or None when the provider failed.

    ``language`` (the app's locale) goes as its ISO-639-1 code. Only the languages
    ``speech.service.STT_ROUTES`` gives Whisper come here, and it takes each of them."""
    audio_format = audio_format_from_filename(filename)
    code = stt_language_code(language)
    try:
        client = get_pooled_client(_TRANSCRIBE_TIMEOUT)

        response = await client.post(
            _OPENROUTER_TRANSCRIBE_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=_payload(model, audio_bytes, audio_format, code),
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenRouter transcription failed model=%s format=%s size=%s status=%s body=%s",
                log_safe(model),
                audio_format,
                len(audio_bytes),
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        data = response.json()
        text = str(data.get("text") or "").strip()
        if not text:
            logger.info(
                "OpenRouter transcription heard no speech model=%s format=%s size=%s",
                log_safe(model),
                audio_format,
                len(audio_bytes),
            )
        # Empty string is a successful silence result. None is reserved for
        # HTTP/provider failures so the router can 502 only those.
        return text
    except Exception:
        logger.exception(
            "Speech transcription failed model=%s format=%s size=%s",
            log_safe(model),
            audio_format,
            len(audio_bytes),
        )
        return None
