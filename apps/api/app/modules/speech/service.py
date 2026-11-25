"""Speech-to-text and TTS product services (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import Settings
from app.gateways import mock_llm, openrouter_speech_gateway, speech_gateway
from app.models import model_catalog
from app.models.model_catalog import openrouter_slug
from app.models.voice_catalog import voice_for
from app.modules.speech.schemas import SPEECH_MAX_AUDIO_BYTES
from app.modules.speech.text_language import UNSURE, clip_language
from app.modules.speech.transcript_validation import sanitize_transcript

logger = logging.getLogger(__name__)

_MAX_TTS_CHARS = 4000
_MOCK_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 64

_STT_ALIAS = "speech-stt-model"
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


async def transcribe_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
    language: str | None = None,
    on_call: Callable[[], None] | None = None,
) -> str | None:
    """The transcript, or None on a failure. ``on_call`` runs just before the provider
    is asked (the mock counts as one): from then on the call may be billed."""
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
    if not settings.openai_api_key:
        return None

    model = (settings.speech_transcription_model or openrouter_slug(_STT_ALIAS)).strip()
    if not speech_gateway.can_transcribe_with(model):
        model = openrouter_slug(_STT_ALIAS)
    if on_call is not None:
        on_call()
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
    voice: str | None = None,
    reply_voice: str | None = None,
    reply_language: str | None = None,
    on_call: Callable[[], None] | None = None,
    on_played: Callable[[ListenClip], None] | None = None,
) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type) of ``text`` played aloud.

    The text's own language picks the model (``text_language``): Kokoro for the languages
    it reads, tts-1 for the rest and for a text whose language is unclear; when Kokoro
    fails, tts-1 reads the clip. ``language`` is the app's locale, ``voice`` the live talk
    voice and ``reply_voice`` the reply voice the user picked (``voice_catalog``);
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
    spoken = clip_language(plain, reply_language)
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
        speaker = voice_for(alias, spoken, reply_voice, voice)
        audio = await _synthesize_with(settings, alias, plain, speaker, language, model_alias)
        if audio is None:
            continue
        logger.info("Listen clip model=%s language=%s chars=%s", alias, spoken, len(plain))
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
