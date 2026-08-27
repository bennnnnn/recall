"""OpenRouter speech STT/TTS HTTP calls (provider boundary)."""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import wave
from collections.abc import AsyncIterator
from pathlib import Path

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
_OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_TRANSCRIBE_TIMEOUT = 60.0
_TTS_TIMEOUT = 60.0
_AUDIO_CHAT_TIMEOUT = 90.0
_LIVE_TALK_VOICE = "alloy"
# OpenAI gpt-audio-* streaming only accepts pcm16 (24 kHz, 16-bit, mono).
_LIVE_TALK_STREAM_FORMAT = "pcm16"
_OPENAI_INPUT_AUDIO_FORMATS = frozenset({"wav", "mp3"})
_DEFAULT_PCM_RATE = 24000
_DEFAULT_PCM_CHANNELS = 1
_PCM_SAMPLE_WIDTH = 2
_MPEG_SYNC = frozenset({0xFB, 0xF3, 0xF2, 0xFA})
_LIVE_TALK_INSTRUCTIONS = (
    "You are Recall, a personal voice assistant. Reply in a natural spoken voice. "
    "Keep answers short unless the user asks for more. No markdown or lists."
)

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


def openai_input_audio_format(filename: str, audio_bytes: bytes) -> str | None:
    """OpenAI chat audio input accepts wav and mp3 only — not m4a/caf."""
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return "wav"
    if audio_bytes[:3] == b"ID3":
        return "mp3"
    if len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and audio_bytes[1] in _MPEG_SYNC:
        return "mp3"
    # Filename is not evidence: Android often writes AAC/MP4 named .wav.
    return None


def live_talk_chat_payload(
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
) -> dict[str, object] | None:
    audio_format = openai_input_audio_format(filename, audio_bytes)
    if audio_format is None:
        return None
    return {
        "model": model,
        "stream": True,
        "modalities": ["text", "audio"],
        "audio": {"voice": _LIVE_TALK_VOICE, "format": _LIVE_TALK_STREAM_FORMAT},
        "messages": [
            {"role": "system", "content": _LIVE_TALK_INSTRUCTIONS},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(audio_bytes).decode("ascii"),
                            "format": audio_format,
                        },
                    }
                ],
            },
        ],
    }


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
            logger.info(
                "OpenRouter transcription heard no speech model=%s format=%s size=%s",
                model,
                audio_format,
                len(audio_bytes),
            )
        # Empty string is a successful silence result. None is reserved for
        # HTTP/provider failures so the router can 502 only those.
        return text
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


def parse_audio_sse_delta(payload: dict[str, object]) -> tuple[str, str]:
    """Pull audio b64 + transcript fragments from one chat-completion SSE object."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ""
    first = choices[0]
    if not isinstance(first, dict):
        return "", ""
    delta = first.get("delta")
    if not isinstance(delta, dict):
        delta = first.get("message")
    if not isinstance(delta, dict):
        return "", ""
    audio = delta.get("audio")
    if not isinstance(audio, dict):
        return "", ""
    data = audio.get("data")
    transcript = audio.get("transcript")
    return (
        data if isinstance(data, str) else "",
        transcript if isinstance(transcript, str) else "",
    )


def decode_joined_audio_b64(fragments: list[str]) -> bytes:
    if not fragments:
        return b""
    joined = "".join(fragments)
    try:
        return base64.b64decode(joined, validate=False)
    except (binascii.Error, ValueError):
        chunks: list[bytes] = []
        for part in fragments:
            try:
                decoded = base64.b64decode(part, validate=False)
            except (binascii.Error, ValueError):
                continue
            if decoded:
                chunks.append(decoded)
        return b"".join(chunks)


async def speech_to_speech_via_openrouter(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
) -> tuple[bytes, str, str] | None:
    """Audio in → spoken audio out via an OpenRouter audio chat model. Not Whisper."""
    payload = live_talk_chat_payload(audio_bytes, filename=filename, model=model)
    if payload is None:
        logger.warning(
            "Live talk input format unsupported filename=%s size=%s magic=%s",
            filename,
            len(audio_bytes),
            audio_bytes[:8].hex(),
        )
        return None
    audio_parts: list[str] = []
    transcript_parts: list[str] = []
    try:
        client = get_pooled_client(_AUDIO_CHAT_TIMEOUT)
        async with client.stream(
            "POST",
            _OPENROUTER_CHAT_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.status_code >= 400:
                error_body = (await response.aread())[:500].decode("utf-8", errors="replace")
                logger.warning(
                    "OpenRouter speech-to-speech failed model=%s status=%s body=%s",
                    model,
                    response.status_code,
                    error_body,
                )
                return None
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(parsed, dict):
                    continue
                stream_error = parsed.get("error")
                if stream_error:
                    logger.warning(
                        "OpenRouter speech-to-speech stream error model=%s body=%s",
                        model,
                        str(stream_error)[:500],
                    )
                    return None
                audio_b64, transcript = parse_audio_sse_delta(parsed)
                if audio_b64:
                    audio_parts.append(audio_b64)
                if transcript:
                    transcript_parts.append(transcript)
    except Exception:
        logger.exception("Speech-to-speech failed model=%s size=%s", model, len(audio_bytes))
        return None

    raw = decode_joined_audio_b64(audio_parts)
    if not raw:
        logger.warning(
            "OpenRouter speech-to-speech returned no audio model=%s transcript_chars=%s",
            model,
            len("".join(transcript_parts)),
        )
        return None
    if raw[:4] != b"RIFF":
        raw = pcm_to_wav(raw)
    return raw, "audio/wav", "".join(transcript_parts).strip()
