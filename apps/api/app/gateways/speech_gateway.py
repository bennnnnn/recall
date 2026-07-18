"""OpenRouter speech STT/TTS HTTP calls (provider boundary)."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
_TRANSCRIBE_TIMEOUT = 60.0
_TTS_TIMEOUT = 60.0

_OPENROUTER_FORMAT_BY_SUFFIX: dict[str, str] = {
    ".m4a": "m4a",
    ".mp3": "mp3",
    ".mp4": "m4a",
    ".wav": "wav",
    ".webm": "webm",
    ".flac": "flac",
    ".caf": "m4a",
    ".3gp": "m4a",
}


def openrouter_audio_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return _OPENROUTER_FORMAT_BY_SUFFIX.get(suffix, suffix.lstrip(".") or "m4a")


async def transcribe_via_openrouter(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
) -> str | None:
    audio_format = openrouter_audio_format(filename)
    payload = {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "format": audio_format,
        },
    }
    try:
        client = get_pooled_client(_TRANSCRIBE_TIMEOUT)
        response = await client.post(
            _OPENROUTER_TRANSCRIBE_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenRouter transcription failed model=%s format=%s size=%s status=%s body=%s",
                model,
                audio_format,
                len(audio_bytes),
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        data = response.json()
        text = str(data.get("text") or "").strip()
        if not text:
            logger.warning(
                "OpenRouter transcription returned empty text model=%s format=%s size=%s",
                model,
                audio_format,
                len(audio_bytes),
            )
        return text or None
    except Exception:
        logger.exception(
            "Speech transcription failed model=%s format=%s size=%s",
            model,
            audio_format,
            len(audio_bytes),
        )
        return None


async def synthesize_via_openrouter(
    settings: Settings,
    text: str,
    *,
    model: str,
    voice: str,
    language: str | None = None,
) -> tuple[bytes, str] | None:
    payload: dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    if language:
        payload["language"] = language
    try:
        client = get_pooled_client(_TTS_TIMEOUT)
        response = await client.post(
            _OPENROUTER_SPEECH_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenRouter TTS failed model=%s status=%s body=%s",
                model,
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        audio = response.content
        if not audio:
            logger.warning("OpenRouter TTS returned empty audio model=%s", model)
            return None
        return audio, "audio/mpeg"
    except Exception:
        logger.exception("Speech TTS failed model=%s chars=%s", model, len(text))
        return None
