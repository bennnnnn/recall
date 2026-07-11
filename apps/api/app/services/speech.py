"""Speech-to-text and TTS product services (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.gateways import mock_llm, speech_gateway

logger = logging.getLogger(__name__)

_MAX_BYTES = 5_000_000
_MAX_TTS_CHARS = 4000
_MOCK_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 64


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
    return await speech_gateway.transcribe_via_openrouter(
        settings,
        audio_bytes,
        filename=filename,
        model=model,
    )


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
    return await speech_gateway.synthesize_via_openrouter(
        settings,
        plain,
        model=model,
        voice=voice,
        language=language,
    )
