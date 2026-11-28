"""Speech-to-text and TTS product services (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import Settings
from app.core.log_text import log_safe
from app.gateways import (
    mock_llm,
    openrouter_speech_gateway,
    speech_gateway,
    transcription_gateway,
)
from app.models import model_catalog
from app.models.model_catalog import openrouter_slug
from app.models.voice_catalog import voice_for
from app.modules.speech.schemas import SPEECH_MAX_AUDIO_BYTES
from app.modules.speech.text_language import UNSURE, clip_language
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


@dataclass(frozen=True)
class ListenClip:
    """What played one Listen clip: the catalog alias, the language it was read in (None:
    unclear) and the call's estimated USD."""

    alias: str
    language: str | None
    usd: float

    @property
    def reply_language(self) -> str:
        """What the rest of the reply should follow: the language, when a model that reads
        only some languages played it; ``UNSURE`` when the any-language model did (unclear
        text, or Kokoro failed), so the rest stays in that one voice too."""
        if self.language is None or model_catalog.speaks(self.alias, None):
            return UNSURE
        return self.language

    @property
    def fell_back(self) -> bool:
        """A model other than its language's first played it: Kokoro failed on a clip in a
        language it reads, and tts-1 played it."""
        if self.language is None:
            return False
        return model_catalog.read_aloud_aliases(self.language)[0] != self.alias


def normalize_tts_alias(raw: str | None) -> str:
    alias = (raw or "").strip()
    if alias in {"tts-model", TTS_QUALITY_ALIAS, ""}:
        return TTS_QUALITY_ALIAS
    if alias == TTS_FAST_ALIAS:
        return TTS_FAST_ALIAS
    return TTS_QUALITY_ALIAS


def resolve_tts_model(settings: Settings, *, alias: str | None = None) -> str:
    """The OpenAI model Listen asks: tts-1, or an operator's OpenAI override; a stale
    non-OpenAI override is ignored."""
    chosen = normalize_tts_alias(alias)
    if chosen == TTS_FAST_ALIAS:
        return openrouter_slug(TTS_FAST_ALIAS)
    raw = (settings.speech_tts_model or openrouter_slug(TTS_QUALITY_ALIAS)).strip()
    if speech_gateway.can_speak_with(raw):
        return raw
    return openrouter_slug(TTS_QUALITY_ALIAS)


@dataclass(frozen=True)
class SttRoute:
    """One transcriber of the recorded clip: its catalog alias, the app languages it takes
    (None: any, and a clip with no language), the spend one clip is estimated at, and how
    long one try may take (None: whatever is left of ``STT_DEADLINE_SECONDS``)."""

    alias: str
    languages: frozenset[str] | None
    spend_usd: float
    try_seconds: float | None = None


# The phone stops waiting for /speech/transcribe at 25 s (``features/speech/api.ts``): every
# try, a fallback included, ends by this, leaving the upload a few seconds.
STT_DEADLINE_SECONDS = 20.0


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
        # A 43 s clip took at most 3.2 s (2026-11-24): a hanging host leaves OpenAI 12 s.
        try_seconds=8.0,
    ),
    SttRoute(
        _STT_OPENAI_LARGE_ALIAS,
        frozenset({"am"}),
        quota_spend.STT_OPENAI_LARGE_SPEND_USD,
        # A 45 s Amharic clip took 5 s: mini still gets 8 s.
        try_seconds=12.0,
    ),
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
    with another of OpenRouter's Whisper models; any other value (``gpt-4o-mini-transcribe``
    from when the clip went to OpenAI directly) uses the catalog's model."""
    override = (settings.speech_transcription_model or "").strip()
    if alias == _STT_ALIAS and transcription_gateway.can_transcribe_with(override):
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

    loop = asyncio.get_running_loop()
    deadline = loop.time() + STT_DEADLINE_SECONDS
    asked = False
    for route in stt_routes_for(language):
        if not model_health.is_available(model_catalog.get(route.alias), settings):
            continue
        left = deadline - loop.time()
        if left <= 0:
            break
        if not asked and on_call is not None:
            on_call()
        asked = True
        if on_spend is not None:
            on_spend(route.spend_usd)
        budget = min(left, route.try_seconds) if route.try_seconds else left
        try:
            async with asyncio.timeout(budget):
                text = await _transcribe_with(settings, route, audio_bytes, filename, language)
        except TimeoutError:
            logger.warning(
                "Speech transcription timed out alias=%s after=%.1fs", route.alias, budget
            )
            text = None
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
    reply_voice: str | None = None,
    reply_language: str | None = None,
    on_call: Callable[[], None] | None = None,
    on_played: Callable[[ListenClip], None] | None = None,
) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type) of ``text`` played aloud.

    The text's own language picks the model (``text_language``): Kokoro for the languages
    it reads, tts-1 for the rest and for a text whose language is unclear; when Kokoro
    fails, tts-1 reads the clip. ``language`` is the app's locale and ``reply_voice`` the reply
    voice the user picked (``voice_catalog``);
    ``reply_language`` is what the reply's lead clip was read as (``clip_language``).
    ``on_call`` runs just before the first provider is asked (the mock counts as one), and
    ``on_played`` with what played the clip (``ListenClip``)."""
    if not settings.speech_tts_enabled:
        return None
    plain = " ".join((text or "").split()).strip()
    if not plain:
        return None
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]
    spoken = clip_language(plain, reply_language, language)
    aliases = [
        alias
        for alias in model_catalog.read_aloud_aliases(spoken)
        if getattr(settings, model_catalog.get(alias).api_key_field, "")
    ]
    # Mock chat must not fake TTS when a key is present: a stub MP3 fails
    # playback and the app falls back to on-device speech.
    if mock_llm.should_mock_llm(settings) and not aliases:
        if on_call is not None:
            on_call()
        return _MOCK_MP3_BYTES, "audio/mpeg"
    if not aliases:
        return None
    if on_call is not None:
        on_call()
    for alias in aliases:
        speaker = voice_for(alias, spoken, reply_voice)
        audio = await _synthesize_with(settings, alias, plain, speaker, language, model_alias)
        if audio is None:
            continue
        logger.info(
            "Listen clip model=%s language=%s chars=%s", alias, log_safe(spoken), len(plain)
        )
        if on_played is not None:
            price = model_catalog.get(alias).usd_per_m_chars or 0.0
            on_played(ListenClip(alias, spoken, len(plain) * price / 1_000_000))
        return audio
    return None


async def _synthesize_with(
    settings: Settings,
    alias: str,
    text: str,
    voice: str,
    language: str | None,
    model_alias: str | None,
) -> tuple[bytes, str] | None:
    """One Listen model's audio of ``text``, by its catalog provider; None when it fails."""
    if model_catalog.get(alias).provider == "openrouter":
        return await openrouter_speech_gateway.synthesize_via_openrouter(
            settings, text, model=openrouter_slug(alias), voice=voice
        )
    return await speech_gateway.synthesize_via_openai(
        settings,
        text,
        model=resolve_tts_model(settings, alias=model_alias),
        voice=voice,
        language=language,
    )
