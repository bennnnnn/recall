"""A voice says its name when the user picks it in Settings → Voice: "Hi, I'm Heart."

The clip is spoken by the engine that will really speak that voice, in the app's language:

* a TTS (reply) voice by the model that plays replies in that language (Kokoro on OpenRouter,
  or tts-1 for Russian, Turkish and Amharic), never by a fallback in another voice;
* a live talk voice by gpt-4o-mini-tts, the OpenAI speech model that has every voice live
  talk's gpt-realtime speaks (tts-1 has no marin, cedar, ballad or verse). It is the same named
  voice; gpt-realtime may deliver a sentence a little differently.

Each (kind, voice, language) clip is made once and kept in Redis for every user. A preview is
not Listen: it takes none of the day's Listen tokens, only a per-minute rate limit.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Callable
from typing import Literal

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import openrouter_speech_gateway, speech_gateway
from app.models import model_catalog
from app.models.voice_catalog import voices_of

logger = logging.getLogger(__name__)

PreviewKind = Literal["reply", "live"]
PREVIEW_ALIAS = "speech-voice-preview-model"
_LIVE_VOICES = frozenset(
    {"marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"}
)
# Bump to make every kept clip again (a new phrase, a new model).
_CACHE_VERSION = 1
_CACHE_TTL_SECONDS = 30 * 24 * 3600
# The line a voice says, by app language: the voice's name is not translated.
_PHRASES = {
    "en": "Hi, I'm {name}.",
    "es": "Hola, soy {name}.",
    "fr": "Bonjour, je suis {name}.",
    "pt": "Olá, eu sou {name}.",
    "ru": "Привет, я {name}.",
    "tr": "Merhaba, ben {name}.",
    "am": "ሰላም፣ እኔ {name} ነኝ።",
    "hi": "नमस्ते, मैं {name} हूँ।",
}


class UnknownVoiceError(ValueError):
    """A voice the engine for this kind and language does not have."""


def voice_name(voice: str) -> str:
    """ "af_heart" -> "Heart", "cedar" -> "Cedar": the name the phone shows."""
    name = voice.split("_", 1)[1] if "_" in voice else voice
    return name[:1].upper() + name[1:]


def preview_line(voice: str, language: str) -> str:
    return _PHRASES.get(language, _PHRASES["en"]).format(name=voice_name(voice))


def preview_engine(kind: PreviewKind, voice: str, language: str) -> str:
    """The catalog alias that speaks ``voice`` for ``kind`` in ``language``; raises
    ``UnknownVoiceError`` for a voice it does not have."""
    if kind == "live":
        if voice not in _LIVE_VOICES:
            raise UnknownVoiceError(voice)
        return PREVIEW_ALIAS
    alias = model_catalog.read_aloud_aliases(language)[0]
    if voice not in {candidate.id for candidate in voices_of(alias, language)}:
        raise UnknownVoiceError(voice)
    return alias


def _cache_key(kind: PreviewKind, voice: str, language: str) -> str:
    return f"speech_preview:v{_CACHE_VERSION}:{kind}:{voice}:{language}"


async def _kept(redis: Redis, key: str) -> tuple[bytes, str] | None:
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return base64.b64decode(data["audio"], validate=True), str(data["content_type"])
    except (ValueError, KeyError, TypeError, binascii.Error):
        return None
    except Exception:
        logger.warning("Voice preview cache read failed", exc_info=True)
        return None


async def _keep(redis: Redis, key: str, audio: bytes, content_type: str) -> None:
    payload = json.dumps(
        {"audio": base64.b64encode(audio).decode("ascii"), "content_type": content_type}
    )
    try:
        await redis.set(key, payload, ex=_CACHE_TTL_SECONDS)
    except Exception:
        logger.warning("Voice preview cache write failed", exc_info=True)


async def _speak(
    settings: Settings, alias: str, text: str, voice: str, language: str
) -> tuple[bytes, str] | None:
    model = model_catalog.get(alias)
    if not getattr(settings, model.api_key_field, ""):
        return None
    slug = model_catalog.openrouter_slug(alias)
    if model.provider == "openrouter":
        return await openrouter_speech_gateway.synthesize_via_openrouter(
            settings, text, model=slug, voice=voice
        )
    return await speech_gateway.synthesize_via_openai(
        settings, text, model=slug, voice=voice, language=language
    )


async def voice_preview(
    settings: Settings,
    redis: Redis,
    *,
    kind: PreviewKind,
    voice: str,
    language: str,
    on_spend: Callable[[float], None] | None = None,
) -> tuple[bytes, str] | None:
    """The clip of ``voice`` saying its name, kept or made once; None when its engine fails
    (never another voice in its place). ``on_spend`` gets a made clip's estimated USD."""
    alias = preview_engine(kind, voice, language)
    key = _cache_key(kind, voice, language)
    kept = await _kept(redis, key)
    if kept is not None:
        return kept
    text = preview_line(voice, language)
    audio = await _speak(settings, alias, text, voice, language)
    if audio is None:
        return None
    await _keep(redis, key, *audio)
    price = model_catalog.get(alias).usd_per_m_chars
    if on_spend is not None and price is not None:
        on_spend(len(text) * price / 1_000_000)
    return audio
