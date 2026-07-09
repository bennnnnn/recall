"""Speech-to-text via OpenRouter (Whisper)."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.core.config import Settings
from app.gateways import mock_llm

logger = logging.getLogger(__name__)

_MAX_BYTES = 5_000_000
_OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_TRANSCRIBE_TIMEOUT = 60.0

# OpenRouter `input_audio.format` values (see openrouter.ai audio transcription docs).
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


def _openrouter_audio_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return _OPENROUTER_FORMAT_BY_SUFFIX.get(suffix, suffix.lstrip(".") or "m4a")


async def transcribe_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
) -> str | None:
    if not settings.speech_transcription_enabled:
        return None
    if not audio_bytes or len(audio_bytes) > _MAX_BYTES:
        logger.warning(
            "Speech transcription rejected: payload size=%s",
            len(audio_bytes) if audio_bytes else 0,
        )
        return None
    if mock_llm.should_mock_llm(settings):
        return "This is a mock transcription."
    if not settings.openrouter_api_key:
        return None

    model = (settings.speech_transcription_model or "openai/whisper-1").strip()
    audio_format = _openrouter_audio_format(filename)
    payload = {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "format": audio_format,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=_TRANSCRIBE_TIMEOUT) as client:
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


_OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
_TTS_TIMEOUT = 60.0
_MAX_TTS_CHARS = 4000
# Tiny MPEG frame placeholder for mock mode (not played in unit tests).
_MOCK_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 64


async def synthesize_speech(
    settings: Settings,
    text: str,
    *,
    language: str | None = None,
) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type) for product alias tts-model."""
    if not settings.speech_tts_enabled:
        return None
    plain = " ".join((text or "").split()).strip()
    if not plain:
        return None
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]
    if mock_llm.should_mock_llm(settings):
        return _MOCK_MP3_BYTES, "audio/mpeg"
    if not settings.openrouter_api_key:
        return None

    model = (settings.speech_tts_model or "openai/gpt-4o-mini-tts").strip()
    voice = (settings.speech_tts_voice or "alloy").strip()
    payload: dict[str, object] = {
        "model": model,
        "input": plain,
        "voice": voice,
        "response_format": "mp3",
    }
    if language:
        payload["language"] = language
    try:
        async with httpx.AsyncClient(timeout=_TTS_TIMEOUT) as client:
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
        logger.exception("Speech TTS failed model=%s chars=%s", model, len(plain))
        return None
