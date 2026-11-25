"""Direct OpenAI recorded-clip transcription and read-aloud HTTP calls (provider boundary).

The clip goes here for the languages Whisper reads badly (``speech.service``); Whisper on
OpenRouter is ``transcription_gateway``.
"""

from __future__ import annotations

import io
import logging
import wave
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.log_text import log_safe
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
_OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
_TRANSCRIBE_TIMEOUT = 20.0
_TTS_TIMEOUT = 60.0
_DEFAULT_PCM_RATE = 24000
# Read aloud speaks with tts-1; gpt-4o-mini-tts stays an operator override (SPEECH_TTS_MODEL).
_SPEECH_MODEL_FAMILIES = ("tts-1", "gpt-4o-mini-tts")
_DEFAULT_PCM_CHANNELS = 1
_PCM_SAMPLE_WIDTH = 2

_AUDIO_FORMAT_BY_SUFFIX: dict[str, str] = {
    ".m4a": "m4a",
    ".mp3": "mp3",
    ".mp4": "m4a",
    ".wav": "wav",
    ".webm": "webm",
    ".flac": "flac",
    ".caf": "m4a",
    ".3gp": "m4a",
}


def can_speak_with(model: str) -> bool:
    """Whether ``model`` (``openai/`` or bare) is one this gateway reads aloud with."""
    return model.removeprefix("openai/").startswith(_SPEECH_MODEL_FAMILIES)


def audio_format_from_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return _AUDIO_FORMAT_BY_SUFFIX.get(suffix, suffix.lstrip(".") or "m4a")


def pcm_to_wav(
    pcm: bytes,
    *,
    sample_rate: int = _DEFAULT_PCM_RATE,
    channels: int = _DEFAULT_PCM_CHANNELS,
) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(max(channels, 1))
        wav.setsampwidth(_PCM_SAMPLE_WIDTH)
        wav.setframerate(sample_rate if sample_rate > 0 else _DEFAULT_PCM_RATE)
        wav.writeframes(pcm)
    return buf.getvalue()


def _parse_pcm_params(content_type: str) -> tuple[int, int]:
    rate, channels = _DEFAULT_PCM_RATE, _DEFAULT_PCM_CHANNELS
    for part in content_type.lower().split(";"):
        token = part.strip()
        if token.startswith("rate="):
            digits = token[5:].strip()
            if digits.isdigit():
                rate = int(digits)
        elif token.startswith("channels="):
            digits = token[9:].strip()
            if digits.isdigit():
                channels = int(digits)
    return rate, channels


def stt_language_code(language: str | None) -> str | None:
    """``language`` (a locale such as ``pt-BR``) as the ISO-639-1 code OpenAI's
    transcription takes, or None when it names none."""
    raw = (language or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    primary = raw.split("-", 1)[0]
    if len(primary) == 2 and primary.isalpha():
        return primary
    return None


# The app's languages by code, for a prompt that names one OpenAI takes no code for.
_LANGUAGE_NAMES: dict[str, str] = {
    "am": "Amharic",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
}
# Codes an OpenAI transcriber refused ("Language code 'am' is not recognized", "Invalid
# value: 'am'"): one memory for every voice path (the recorded clip, live dictation, live
# talk's own words), so each names that language in its prompt instead of sending a code
# that fails. A process cache that only grows; it holds no user's data.
_REFUSED_LANGUAGES: set[str] = set()


def stt_language_name(code: str | None) -> str | None:
    """The English name of one of the app's languages, by its ISO-639-1 code."""
    return _LANGUAGE_NAMES.get((code or "").strip().lower())


def stt_language_hint(language: str | None) -> tuple[str | None, str]:
    """How a transcription names the app's language: the ISO code to send, or, for a code
    OpenAI refused, None and a prompt sentence naming the language ("" when there is none)."""
    code = stt_language_code(language)
    if not code:
        return None, ""
    if code not in _REFUSED_LANGUAGES:
        return code, ""
    name = stt_language_name(code)
    return None, f"The speaker speaks {name}: write it in {name}'s own script." if name else ""


def mark_stt_language_refused(code: str) -> None:
    """OpenAI refused this code: every voice path names the language from now on."""
    _REFUSED_LANGUAGES.add(code)


def _transcription_payload(model: str, language: str | None) -> dict[str, str]:
    payload: dict[str, str] = {"model": model.removeprefix("openai/"), "response_format": "json"}
    code, prompt = stt_language_hint(language)
    if code:
        payload["language"] = code
    elif prompt:
        payload["prompt"] = prompt
    return payload


async def transcribe_via_openai(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
    language: str | None = None,
) -> str | None:
    audio_format = audio_format_from_filename(filename)
    payload = _transcription_payload(model, language)
    try:
        client = get_pooled_client(_TRANSCRIBE_TIMEOUT)

        async def post(data: dict[str, str]) -> httpx.Response:
            return await client.post(
                _OPENAI_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data=data,
                files={"file": (Path(filename).name, audio_bytes)},
            )

        response = await post(payload)
        refused = payload.get("language")
        if response.status_code == 400 and refused and "language" in response.text:
            # Amharic's "am" came back 400 and every Amharic dictation failed.
            # The code is never logged: it came from the phone.
            logger.warning("OpenAI transcription refused the language; naming it instead")
            mark_stt_language_refused(refused)
            response = await post(_transcription_payload(model, language))
        if response.status_code >= 400:
            logger.warning(
                "OpenAI transcription failed model=%s format=%s size=%s status=%s body=%s",
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
                "OpenAI transcription heard no speech model=%s format=%s size=%s",
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


def _tts_request_payload(
    *,
    model: str,
    text: str,
    voice: str,
    response_format: str,
    language: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model.removeprefix("openai/"),
        "input": text,
        "voice": voice,
        "response_format": response_format,
    }
    # Only the gpt-4o voices take instructions; tts-1 reads the language from the text.
    if model.removeprefix("openai/").startswith("gpt-4o"):
        payload["instructions"] = _openai_tts_instructions(language)
    return payload


def _openai_tts_instructions(language: str | None) -> str:
    base = "Speak clearly and naturally, as a helpful assistant reading a message aloud."
    locale = (language or "").strip()
    if not locale:
        return base
    return f"{base} Use a natural voice appropriate for locale {locale}."


async def synthesize_via_openai(
    settings: Settings,
    text: str,
    *,
    model: str,
    voice: str,
    language: str | None = None,
) -> tuple[bytes, str] | None:
    # Locale is a voice instruction, not an unsupported `language` field.
    response_format = "mp3"
    payload = _tts_request_payload(
        model=model,
        text=text,
        voice=voice,
        response_format=response_format,
        language=language,
    )
    try:
        client = get_pooled_client(_TTS_TIMEOUT)
        response = await client.post(
            _OPENAI_SPEECH_URL,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenAI TTS failed model=%s status=%s body=%s",
                log_safe(model),
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        audio = response.content
        if not audio:
            logger.warning("OpenAI TTS returned empty audio model=%s", log_safe(model))
            return None
        header_type = (response.headers.get("content-type") or "").lower()
        content_type = header_type.split(";")[0].strip()
        looks_pcm = "pcm" in header_type or (
            response_format == "pcm"
            and "mpeg" not in header_type
            and "mp3" not in header_type
            and "wav" not in header_type
        )
        if looks_pcm:
            rate, channels = _parse_pcm_params(header_type)
            return pcm_to_wav(audio, sample_rate=rate, channels=channels), "audio/wav"
        return audio, content_type or "audio/mpeg"
    except Exception:
        logger.exception("Speech TTS failed model=%s chars=%s", log_safe(model), len(text))
        return None
