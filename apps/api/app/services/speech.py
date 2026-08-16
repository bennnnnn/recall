"""Speech-to-text and TTS product services (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.gateways import mock_llm, speech_gateway
from app.services.model_catalog import openrouter_slug

logger = logging.getLogger(__name__)

_MAX_BYTES = 5_000_000
_MAX_TTS_CHARS = 4000
_MOCK_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 64

_STT_ALIAS = "speech-stt-model"
TTS_QUALITY_ALIAS = "speech-tts-model"
TTS_FAST_ALIAS = "speech-tts-fast-model"
# OpenAI GPT TTS is not listed on OpenRouter anymore (400 "does not exist").
_RETIRED_TTS_SLUGS = frozenset(
    {
        "openai/gpt-4o-mini-tts",
        "gpt-4o-mini-tts",
        "openai/gpt-4o-mini-tts-2025-12-15",
    }
)
_OPENAI_TTS_VOICES = frozenset({"alloy", "echo", "fable", "onyx", "nova", "shimmer"})


def normalize_tts_alias(raw: str | None) -> str:
    alias = (raw or "").strip()
    if alias in {"tts-model", TTS_QUALITY_ALIAS, ""}:
        return TTS_QUALITY_ALIAS
    if alias == TTS_FAST_ALIAS:
        return TTS_FAST_ALIAS
    return TTS_QUALITY_ALIAS


def default_voice_for_slug(model: str) -> str:
    slug = model.lower()
    if slug.startswith("google/") or "gemini" in slug:
        return "Kore"
    if "kokoro" in slug:
        return "af_alloy"
    if slug.startswith("openai/"):
        return "alloy"
    return "Kore"


def resolve_tts_model(settings: Settings, *, alias: str | None = None) -> str:
    """OpenRouter TTS slug for a product alias (Gemini default, Kokoro fast)."""
    chosen = normalize_tts_alias(alias)
    if chosen == TTS_FAST_ALIAS:
        return openrouter_slug(TTS_FAST_ALIAS)
    raw = (settings.speech_tts_model or openrouter_slug(TTS_QUALITY_ALIAS)).strip()
    if raw in _RETIRED_TTS_SLUGS:
        return openrouter_slug(TTS_QUALITY_ALIAS)
    return raw


def resolve_tts_voice(settings: Settings, model: str) -> str:
    """Voice id valid for the resolved OpenRouter TTS slug."""
    default = default_voice_for_slug(model)
    voice = (settings.speech_tts_voice or "").strip()
    if not voice:
        return default
    leftover = voice.lower() in _OPENAI_TTS_VOICES or voice.lower() == "kore"
    if leftover:
        if model.startswith("openai/") and voice.lower() in _OPENAI_TTS_VOICES:
            return voice
        if voice.lower() == "kore" and (model.startswith("google/") or "gemini" in model.lower()):
            return voice
        return default
    return voice


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

    model = (settings.speech_transcription_model or openrouter_slug(_STT_ALIAS)).strip()
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
    model_alias: str | None = None,
) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type) for Gemini or Kokoro TTS."""
    if not settings.speech_tts_enabled:
        return None
    plain = " ".join((text or "").split()).strip()
    if not plain:
        return None
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]
    # Mock chat must not fake TTS when a key is present: a stub MP3 fails
    # playback and the app falls back to on-device speech.
    if mock_llm.should_mock_llm(settings) and not settings.openrouter_api_key:
        return _MOCK_MP3_BYTES, "audio/mpeg"
    if not settings.openrouter_api_key:
        return None

    model = resolve_tts_model(settings, alias=model_alias)
    voice = resolve_tts_voice(settings, model)
    return await speech_gateway.synthesize_via_openrouter(
        settings,
        plain,
        model=model,
        voice=voice,
        language=language,
    )


async def iter_tts_pcm(
    settings: Settings,
    text: str,
    *,
    language: str | None = None,
    model_alias: str | None = None,
) -> AsyncIterator[bytes]:
    """Yield PCM bytes as they arrive from OpenRouter (empty if synthesis fails)."""
    if not settings.speech_tts_enabled:
        return
    plain = " ".join((text or "").split()).strip()
    if not plain:
        return
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]
    if mock_llm.should_mock_llm(settings) and not settings.openrouter_api_key:
        # 50ms of silence so the stream endpoint can be tested without a key.
        yield b"\x00\x00" * 1200
        return
    if not settings.openrouter_api_key:
        return

    model = resolve_tts_model(settings, alias=model_alias)
    voice = resolve_tts_voice(settings, model)
    async for chunk in speech_gateway.stream_pcm_via_openrouter(
        settings,
        plain,
        model=model,
        voice=voice,
        language=language,
    ):
        yield chunk
