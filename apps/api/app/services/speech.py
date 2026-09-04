"""Speech-to-text and TTS product services (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.gateways import mock_llm, speech_gateway
from app.models.schemas.integrations import SPEECH_MAX_AUDIO_BYTES
from app.services.model_catalog import openrouter_slug
from app.services.transcript_validation import sanitize_transcript

logger = logging.getLogger(__name__)

_MAX_TTS_CHARS = 4000
_MOCK_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 64

_STT_ALIAS = "speech-stt-model"
TTS_QUALITY_ALIAS = "speech-tts-model"
TTS_FAST_ALIAS = "speech-tts-fast-model"
LIVE_TALK_ALIAS = "live-talk-model"
_OPENAI_TTS_VOICES = frozenset(
    {
        "alloy",
        "echo",
        "fable",
        "onyx",
        "nova",
        "shimmer",
        "ash",
        "ballad",
        "coral",
        "sage",
        "verse",
        "marin",
        "cedar",
    }
)
_TTS_LEAD_MIN_CHARS = 120
_TTS_LEAD_MAX_CHARS = 160
_TTS_SENTENCE_ENDS = frozenset(".!?")


def split_tts_lead(plain: str) -> tuple[str, str]:
    """Opening chunk: long enough to speak while the rest synthesizes."""
    normalized = " ".join((plain or "").split()).strip()
    if not normalized:
        return "", ""
    if len(normalized) <= _TTS_LEAD_MIN_CHARS:
        return normalized, ""
    window = normalized[:_TTS_LEAD_MAX_CHARS]
    cut = -1
    for index, char in enumerate(window):
        if char not in _TTS_SENTENCE_ENDS:
            continue
        if index + 1 < len(window) and window[index + 1] != " ":
            continue
        cut = index + 1
        if cut >= _TTS_LEAD_MIN_CHARS:
            break
    if cut < _TTS_LEAD_MIN_CHARS:
        space = window.rfind(" ")
        cut = space if space > 0 else _TTS_LEAD_MAX_CHARS
    lead = normalized[:cut].strip()
    rest = normalized[cut:].strip()
    if not rest:
        return normalized, ""
    return lead, rest


def normalize_tts_alias(raw: str | None) -> str:
    alias = (raw or "").strip()
    if alias in {"tts-model", TTS_QUALITY_ALIAS, ""}:
        return TTS_QUALITY_ALIAS
    if alias == TTS_FAST_ALIAS:
        return TTS_FAST_ALIAS
    return TTS_QUALITY_ALIAS


def resolve_tts_model(settings: Settings, *, alias: str | None = None) -> str:
    """Both read-aloud aliases use OpenAI; ignore stale non-OpenAI overrides."""
    chosen = normalize_tts_alias(alias)
    if chosen == TTS_FAST_ALIAS:
        return openrouter_slug(TTS_FAST_ALIAS)
    raw = (settings.speech_tts_model or openrouter_slug(TTS_QUALITY_ALIAS)).strip()
    if raw.removeprefix("openai/").startswith("gpt-4o-mini-tts"):
        return raw
    return openrouter_slug(TTS_QUALITY_ALIAS)


def resolve_tts_voice(settings: Settings, model: str) -> str:
    """Reject voices left over from Gemini/Kokoro configuration."""
    voice = (settings.speech_tts_voice or "").strip().lower()
    return voice if voice in _OPENAI_TTS_VOICES else "alloy"


async def transcribe_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
    language: str | None = None,
) -> str | None:
    if not settings.speech_transcription_enabled:
        return None
    if not audio_bytes or len(audio_bytes) > SPEECH_MAX_AUDIO_BYTES:
        logger.warning(
            "Speech transcription rejected: payload size=%s",
            len(audio_bytes) if audio_bytes else 0,
        )
        return None
    if mock_llm.should_mock_llm(settings):
        return "This is a mock transcription."
    if not settings.openai_api_key:
        return None

    model = (settings.speech_transcription_model or openrouter_slug(_STT_ALIAS)).strip()
    if model.removeprefix("openai/") not in {"gpt-4o-mini-transcribe", "gpt-4o-transcribe"}:
        model = openrouter_slug(_STT_ALIAS)
    text = await speech_gateway.transcribe_via_openai(
        settings,
        audio_bytes,
        filename=filename,
        model=model,
        language=language,
    )
    if text is None:
        return None
    return sanitize_transcript(text, audio_size=len(audio_bytes))


async def synthesize_speech(
    settings: Settings,
    text: str,
    *,
    language: str | None = None,
    model_alias: str | None = None,
) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type) for OpenAI TTS."""
    if not settings.speech_tts_enabled:
        return None
    plain = " ".join((text or "").split()).strip()
    if not plain:
        return None
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]
    # Mock chat must not fake TTS when a key is present: a stub MP3 fails
    # playback and the app falls back to on-device speech.
    if mock_llm.should_mock_llm(settings) and not settings.openai_api_key:
        return _MOCK_MP3_BYTES, "audio/mpeg"
    if not settings.openai_api_key:
        return None

    model = resolve_tts_model(settings, alias=model_alias)
    voice = resolve_tts_voice(settings, model)
    return await speech_gateway.synthesize_via_openai(
        settings,
        plain,
        model=model,
        voice=voice,
        language=language,
    )


async def _collect_pcm(
    settings: Settings,
    text: str,
    *,
    model: str,
    voice: str,
    language: str | None,
) -> list[bytes]:
    chunks: list[bytes] = []
    async for chunk in speech_gateway.stream_pcm_via_openai(
        settings,
        text,
        model=model,
        voice=voice,
        language=language,
    ):
        if chunk:
            chunks.append(chunk)
    return chunks


async def iter_tts_pcm(
    settings: Settings,
    text: str,
    *,
    language: str | None = None,
    model_alias: str | None = None,
) -> AsyncIterator[bytes]:
    """Yield lead-sentence PCM first, then the rest (empty if synthesis fails)."""
    if not settings.speech_tts_enabled:
        return
    plain = " ".join((text or "").split()).strip()
    if not plain:
        return
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]
    lead, rest = split_tts_lead(plain)
    if mock_llm.should_mock_llm(settings) and not settings.openai_api_key:
        yield b"\x00\x00" * 1200
        if rest:
            yield b"\x00\x00" * 400
        return
    if not settings.openai_api_key:
        return

    model = resolve_tts_model(settings, alias=model_alias)
    voice = resolve_tts_voice(settings, model)
    rest_task: asyncio.Task[list[bytes]] | None = None
    if rest:
        rest_task = asyncio.create_task(
            _collect_pcm(
                settings,
                rest,
                model=model,
                voice=voice,
                language=language,
            )
        )
    try:
        async for chunk in speech_gateway.stream_pcm_via_openai(
            settings,
            lead,
            model=model,
            voice=voice,
            language=language,
        ):
            if chunk:
                yield chunk
        if rest_task is None:
            return
        for chunk in await rest_task:
            yield chunk
    finally:
        if rest_task is not None and not rest_task.done():
            rest_task.cancel()
            try:
                await rest_task
            except asyncio.CancelledError:
                logger.debug("Cancelled in-flight rest TTS after stream close")
