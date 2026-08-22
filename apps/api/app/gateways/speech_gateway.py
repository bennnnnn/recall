"""OpenRouter speech STT/TTS HTTP calls (provider boundary)."""

from __future__ import annotations

import base64
import io
import logging
import wave
from collections.abc import AsyncIterator
from pathlib import Path

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
_TRANSCRIBE_TIMEOUT = 60.0
_TTS_TIMEOUT = 60.0
_DEFAULT_PCM_RATE = 24000
_DEFAULT_PCM_CHANNELS = 1
_PCM_SAMPLE_WIDTH = 2

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


def tts_response_format(model: str) -> str:
    slug = model.lower()
    if slug.startswith("google/") or "gemini" in slug:
        return "pcm"
    return "mp3"


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


def _tts_request_payload(
    *,
    model: str,
    text: str,
    voice: str,
    response_format: str,
    language: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": response_format,
    }
    if model.startswith("openai/"):
        payload["provider"] = {
            "options": {
                "openai": {"instructions": _openai_tts_instructions(language)},
            }
        }
    return payload


def _openai_tts_instructions(language: str | None) -> str:
    base = "Speak clearly and naturally, as a helpful assistant reading a message aloud."
    locale = (language or "").strip()
    if not locale:
        return base
    return f"{base} Use a natural voice appropriate for locale {locale}."


async def synthesize_via_openrouter(
    settings: Settings,
    text: str,
    *,
    model: str,
    voice: str,
    language: str | None = None,
) -> tuple[bytes, str] | None:
    # OpenRouter /audio/speech is OpenAI-compatible: model, input, voice,
    # response_format. A `language` field 400s and the app falls back to
    # on-device speech — pass locale only as OpenAI voice instructions.
    response_format = tts_response_format(model)
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
        logger.exception("Speech TTS failed model=%s chars=%s", model, len(text))
        return None


async def stream_pcm_via_openrouter(
    settings: Settings,
    text: str,
    *,
    model: str,
    voice: str,
    language: str | None = None,
) -> AsyncIterator[bytes]:
    """Yield PCM (or raw audio) as OpenRouter produces it — do not buffer the clip."""
    payload = _tts_request_payload(
        model=model,
        text=text,
        voice=voice,
        response_format="pcm",
        language=language,
    )
    try:
        client = get_pooled_client(_TTS_TIMEOUT)
        async with client.stream(
            "POST",
            _OPENROUTER_SPEECH_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.status_code >= 400:
                error_body = (await response.aread())[:500].decode("utf-8", errors="replace")
                logger.warning(
                    "OpenRouter TTS stream failed model=%s status=%s body=%s",
                    model,
                    response.status_code,
                    error_body,
                )
                return
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk
    except Exception:
        logger.exception("Speech TTS stream failed model=%s chars=%s", model, len(text))
        return
