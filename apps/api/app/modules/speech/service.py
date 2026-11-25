"""Speech-to-text and TTS product services (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import Settings
from app.gateways import mock_llm, speech_gateway, transcription_gateway
from app.models import model_catalog
from app.models.model_catalog import openrouter_slug
from app.modules.speech.schemas import SPEECH_MAX_AUDIO_BYTES
from app.modules.speech.transcript_validation import sanitize_transcript
from app.services import model_health
from app.services.quota import spend as quota_spend

logger = logging.getLogger(__name__)

_MAX_TTS_CHARS = 4000
_MOCK_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 64

_STT_ALIAS = "speech-stt-model"
_STT_OPENAI_ALIAS = "speech-stt-openai-model"
_STT_OPENAI_LARGE_ALIAS = "speech-stt-openai-large-model"
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
    if speech_gateway.can_speak_with(raw):
        return raw
    return openrouter_slug(TTS_QUALITY_ALIAS)


def resolve_tts_voice(settings: Settings, model: str, user_voice: str | None = None) -> str:
    """The user's voice, else the configured one; never one left from Gemini/Kokoro."""
    chosen = (user_voice or "").strip().lower()
    if chosen not in _OPENAI_TTS_VOICES:
        configured = (settings.speech_tts_voice or "").strip().lower()
        chosen = configured if configured in _OPENAI_TTS_VOICES else "alloy"
    # The model may lack the voice (it is live talk's choice too): the gateway picks its nearest.
    return speech_gateway.voice_for(model, chosen)


@dataclass(frozen=True)
class SttRoute:
    """One transcriber of the recorded clip: its catalog alias, the app languages it takes
    (None: any, and a clip with no language) and the spend one clip is estimated at."""

    alias: str
    languages: frozenset[str] | None
    spend_usd: float


# Tried in order; a clip goes to every route that takes its language until one answers.
# Whisper read English and Spanish right and Amharic as garbage, and misspelt Hindi
# (2026-11-24): it takes only the languages below. gpt-4o-mini-transcribe wrote Amharic in
# Latin letters and gpt-4o-transcribe in Ethiopic, so Amharic goes to the larger one.
# gpt-4o-mini-transcribe takes the rest, a clip with no language, and any clip the routes
# before it failed.
STT_ROUTES: tuple[SttRoute, ...] = (
    SttRoute(
        _STT_ALIAS,
        frozenset({"en", "es", "fr", "pt", "ru", "tr"}),
        quota_spend.STT_WHISPER_SPEND_USD,
    ),
    SttRoute(_STT_OPENAI_LARGE_ALIAS, frozenset({"am"}), quota_spend.STT_OPENAI_LARGE_SPEND_USD),
    SttRoute(_STT_OPENAI_ALIAS, None, quota_spend.STT_OPENAI_SPEND_USD),
)


def stt_routes_for(language: str | None) -> tuple[SttRoute, ...]:
    """The routes a clip in ``language`` (the app's locale) is offered to, in order."""
    code = speech_gateway.stt_language_code(language)
    return tuple(
        route for route in STT_ROUTES if route.languages is None or code in route.languages
    )


def resolve_stt_model(settings: Settings, alias: str = _STT_ALIAS) -> str:
    """The model a route's alias sends. ``SPEECH_TRANSCRIPTION_MODEL`` overrides Whisper's
    with another OpenRouter slug; one with no provider part (``gpt-4o-mini-transcribe``)
    is no OpenRouter id, so the catalog's model is used instead."""
    override = (settings.speech_transcription_model or "").strip()
    if alias == _STT_ALIAS and "/" in override:
        return override
    return openrouter_slug(alias)


async def _transcribe_with(
    settings: Settings, route: SttRoute, audio_bytes: bytes, filename: str, language: str | None
) -> str | None:
    entry = model_catalog.get(route.alias)
    # The catalog entry's key names the provider, and so the gateway that calls it.
    call = (
        transcription_gateway.transcribe_via_openrouter
        if entry.api_key_field == model_catalog.OPENROUTER_KEY
        else speech_gateway.transcribe_via_openai
    )
    return await call(
        settings,
        audio_bytes,
        filename=filename,
        model=resolve_stt_model(settings, route.alias),
        language=language,
    )


async def transcribe_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
    language: str | None = None,
    on_call: Callable[[], None] | None = None,
    on_spend: Callable[[float], None] | None = None,
) -> str | None:
    """The transcript, or None on a failure. ``on_call`` runs just before the provider
    is first asked (the mock counts as one): from then on the call may be billed.
    ``on_spend`` gets each asked transcriber's estimated cost (``STT_ROUTES``)."""
    if not settings.speech_transcription_enabled:
        return None
    if not audio_bytes or len(audio_bytes) > SPEECH_MAX_AUDIO_BYTES:
        logger.warning(
            "Speech transcription rejected: payload size=%s",
            len(audio_bytes) if audio_bytes else 0,
        )
        return None
    if mock_llm.should_mock_llm(settings):
        if on_call is not None:
            on_call()
        return "This is a mock transcription."

    asked = False
    for route in stt_routes_for(language):
        if not model_health.is_available(model_catalog.get(route.alias), settings):
            continue
        if not asked and on_call is not None:
            on_call()
        asked = True
        if on_spend is not None:
            on_spend(route.spend_usd)
        text = await _transcribe_with(settings, route, audio_bytes, filename, language)
        if text is not None:
            return sanitize_transcript(text, audio_size=len(audio_bytes))
        logger.warning("Speech transcription route failed alias=%s", route.alias)
    return None


async def synthesize_speech(
    settings: Settings,
    text: str,
    *,
    language: str | None = None,
    model_alias: str | None = None,
    voice: str | None = None,
    on_call: Callable[[], None] | None = None,
) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type) for OpenAI TTS.

    ``on_call`` runs just before the provider is asked (the mock counts as one)."""
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
        if on_call is not None:
            on_call()
        return _MOCK_MP3_BYTES, "audio/mpeg"
    if not settings.openai_api_key:
        return None

    model = resolve_tts_model(settings, alias=model_alias)
    if on_call is not None:
        on_call()
    return await speech_gateway.synthesize_via_openai(
        settings,
        plain,
        model=model,
        voice=resolve_tts_voice(settings, model, voice),
        language=language,
    )
