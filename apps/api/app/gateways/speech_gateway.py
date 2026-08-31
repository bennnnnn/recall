"""OpenRouter speech STT/TTS HTTP calls (provider boundary)."""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import time
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
    "Answer in one or two short sentences unless the user asks for more. "
    "No markdown, lists, or spelling-aloud."
)
_LIVE_TALK_HISTORY_MAX = 10
_LIVE_TALK_HISTORY_CHARS = 600

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
    history: list[tuple[str, str]] | None = None,
) -> dict[str, object] | None:
    audio_format = openai_input_audio_format(filename, audio_bytes)
    if audio_format is None:
        return None
    messages: list[dict[str, object]] = [
        {"role": "system", "content": _LIVE_TALK_INSTRUCTIONS},
    ]
    for role, content in (history or [])[-_LIVE_TALK_HISTORY_MAX:]:
        if role not in {"user", "assistant"}:
            continue
        text = " ".join((content or "").split()).strip()[:_LIVE_TALK_HISTORY_CHARS]
        if not text:
            continue
        messages.append({"role": role, "content": text})
    messages.append(
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
        }
    )
    return {
        "model": model,
        "stream": True,
        "modalities": ["text", "audio"],
        "audio": {"voice": _LIVE_TALK_VOICE, "format": _LIVE_TALK_STREAM_FORMAT},
        "messages": messages,
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
    audio_b64 = ""
    transcript = ""
    audio = delta.get("audio")
    if isinstance(audio, dict):
        data = audio.get("data")
        audio_b64 = data if isinstance(data, str) else ""
        text = audio.get("transcript")
        transcript = text if isinstance(text, str) else ""
    if not transcript:
        content = delta.get("content")
        transcript = content if isinstance(content, str) else ""
    return audio_b64, transcript


def merge_stream_transcript(current: str, incoming: str) -> str:
    """OpenAI may send cumulative or incremental transcript deltas."""
    if not incoming:
        return current
    if not current:
        return incoming
    if incoming.startswith(current):
        return incoming
    if current.endswith(incoming):
        return current
    return current + incoming


def decode_audio_b64_incremental(pending: str, fragment: str) -> tuple[bytes, str]:
    """Decode complete base64 quartets; keep a remainder for the next chunk."""
    buffer = f"{pending}{fragment}"
    complete = len(buffer) - (len(buffer) % 4)
    if complete <= 0:
        return b"", buffer
    try:
        decoded = base64.b64decode(buffer[:complete], validate=False)
    except (binascii.Error, ValueError):
        return b"", buffer
    return decoded, buffer[complete:]


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


def riff_payload_complete(data: bytes | bytearray) -> bool:
    if len(data) < 8 or bytes(data[:4]) != b"RIFF":
        return False
    declared = int.from_bytes(data[4:8], "little") + 8
    return declared >= 12 and len(data) >= declared


def wav_pcm_frames(data: bytes) -> bytes | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as src:
            if src.getsampwidth() != _PCM_SAMPLE_WIDTH:
                return None
            return src.readframes(src.getnframes())
    except wave.Error:
        return None


def take_live_talk_pcm(stash: bytearray, incoming: bytes) -> bytes:
    """Normalize OpenRouter audio bytes to pcm16. Do not play a WAV file as samples."""
    if incoming:
        stash.extend(incoming)
    if not stash:
        return b""
    if len(stash) >= 2 and (stash[:3] == b"ID3" or (stash[0] == 0xFF and stash[1] in _MPEG_SYNC)):
        logger.warning("Live talk OpenRouter sent MPEG instead of pcm16; dropping")
        stash.clear()
        return b""
    if len(stash) < 4:
        return b""
    if stash[:4] == b"RIFF":
        if len(stash) < 12:
            return b""
        if stash[8:12] != b"WAVE":
            n = (len(stash) // 2) * 2
            out = bytes(stash[:n])
            del stash[:n]
            return out
        if not riff_payload_complete(stash):
            return b""
        declared = int.from_bytes(stash[4:8], "little") + 8
        blob = bytes(stash[:declared])
        del stash[:declared]
        frames = wav_pcm_frames(blob)
        if frames is None:
            logger.warning("Live talk WAV unwrap failed size=%s", len(blob))
            return b""
        return frames
    n = (len(stash) // 2) * 2
    out = bytes(stash[:n])
    del stash[:n]
    return out


async def iter_speech_to_speech_via_openrouter(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
    history: list[tuple[str, str]] | None = None,
) -> AsyncIterator[tuple[bytes, str]]:
    """Yield (pcm_chunk, transcript_so_far) as OpenRouter streams. Do not buffer the clip."""
    payload = live_talk_chat_payload(audio_bytes, filename=filename, model=model, history=history)
    if payload is None:
        logger.warning(
            "Live talk input format unsupported filename=%s size=%s magic=%s",
            filename,
            len(audio_bytes),
            audio_bytes[:8].hex(),
        )
        return
    transcript = ""
    b64_rest = ""
    pcm_stash = bytearray()
    started = time.perf_counter()
    first_pcm_logged = False
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
                return
            logger.info(
                "Live talk OpenRouter headers after %.0fms model=%s status=%s",
                (time.perf_counter() - started) * 1000,
                model,
                response.status_code,
            )
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
                    return
                audio_b64, piece = parse_audio_sse_delta(parsed)
                if piece:
                    transcript = merge_stream_transcript(transcript, piece)
                pcm = b""
                if audio_b64:
                    decoded, b64_rest = decode_audio_b64_incremental(b64_rest, audio_b64)
                    pcm = take_live_talk_pcm(pcm_stash, decoded)
                if pcm and not first_pcm_logged:
                    first_pcm_logged = True
                    logger.info(
                        "Live talk OpenRouter first PCM after %.0fms model=%s bytes=%s",
                        (time.perf_counter() - started) * 1000,
                        model,
                        len(pcm),
                    )
                if pcm or piece:
                    yield pcm, transcript
            if b64_rest:
                pad = "=" * ((4 - len(b64_rest) % 4) % 4)
                try:
                    extra = base64.b64decode(b64_rest + pad, validate=False)
                except (binascii.Error, ValueError):
                    extra = b""
                extra_pcm = take_live_talk_pcm(pcm_stash, extra)
                if extra_pcm:
                    yield extra_pcm, transcript
            leftover = take_live_talk_pcm(pcm_stash, b"")
            if leftover:
                yield leftover, transcript
    except Exception:
        logger.exception("Speech-to-speech failed model=%s size=%s", model, len(audio_bytes))
        return


async def speech_to_speech_via_openrouter(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    model: str,
    history: list[tuple[str, str]] | None = None,
) -> tuple[bytes, str, str] | None:
    """Audio in → spoken audio out via an OpenRouter audio chat model. Not Whisper."""
    pcm_parts: list[bytes] = []
    transcript = ""
    async for pcm, text in iter_speech_to_speech_via_openrouter(
        settings,
        audio_bytes,
        filename=filename,
        model=model,
        history=history,
    ):
        if pcm:
            pcm_parts.append(pcm)
        if text:
            transcript = text
    raw = b"".join(pcm_parts)
    if not raw:
        logger.warning(
            "OpenRouter speech-to-speech returned no audio model=%s transcript_chars=%s",
            model,
            len(transcript),
        )
        return None
    if raw[:4] != b"RIFF":
        raw = pcm_to_wav(raw)
    return raw, "audio/wav", transcript.strip()
