"""Stream live-talk replies (Whisper, then a short spoken text turn)."""

from __future__ import annotations

import io
import logging
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.gateways import mock_llm, speech_gateway
from app.gateways.litellm_gateway import stream_chat_completion
from app.models.schemas.integrations import SPEECH_MAX_AUDIO_BYTES
from app.services.model_catalog import auto_fast_alias
from app.services.speech import (
    resolve_live_talk_model,
    transcribe_audio,
)

logger = logging.getLogger(__name__)

# 24 kHz 16-bit mono. Larger clips mean fewer player restarts (clicks) on device.
_LIVE_TALK_FIRST_CLIP_PCM = 24000 * 2 // 2  # 0.5s
_LIVE_TALK_CLIP_PCM = 24000 * 2 * 3 // 2  # 1.5s
_SILENCE_ABS = 512
_SILENCE_PAD_MS = 80
_SILENCE_MIN_MS = 300
_SPOKEN_REPLY_MAX_TOKENS = 180
_SPOKEN_REPLY_HISTORY = 10
_SPOKEN_REPLY_TURN_CHARS = 600
_SPOKEN_REPLY_SYSTEM = (
    "You are Recall, a personal voice assistant. Reply in a natural spoken voice. "
    "Answer in one or two short sentences unless the user asks for more. "
    "No markdown, lists, or spelling-aloud."
)


LIVE_TALK_EMPTY_TRANSCRIPT = "empty_transcript"


@dataclass(frozen=True, slots=True)
class LiveTalkStreamEvent:
    kind: Literal["user", "assistant", "audio", "error"]
    text: str = ""
    audio_wav: bytes = b""


def _pcm16_abs(pcm: bytes | bytearray, offset: int) -> int:
    sample = int.from_bytes(pcm[offset : offset + 2], "little", signed=True)
    return -sample if sample < 0 else sample


def trim_wav_silence(audio_bytes: bytes) -> bytes:
    """Drop leading/trailing near-silence so GPT Audio is not fed a long quiet file."""
    if len(audio_bytes) < 44 or audio_bytes[:4] != b"RIFF":
        return audio_bytes
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as src:
            channels = src.getnchannels()
            width = src.getsampwidth()
            rate = src.getframerate()
            frames = src.readframes(src.getnframes())
    except wave.Error:
        return audio_bytes
    if width != 2 or rate <= 0 or channels <= 0 or not frames:
        return audio_bytes
    sample_count = len(frames) // 2
    first: int | None = None
    last = 0
    for i in range(sample_count):
        if _pcm16_abs(frames, i * 2) > _SILENCE_ABS:
            if first is None:
                first = i
            last = i
    pad = max(0, int(rate * _SILENCE_PAD_MS / 1000) * channels)
    if first is None:
        max_samples = max(1, int(rate * _SILENCE_MIN_MS / 1000) * channels)
        clipped = frames[: max_samples * width]
        return speech_gateway.pcm_to_wav(clipped, sample_rate=rate, channels=channels)
    start = max(0, first - pad)
    end = min(sample_count, last + 1 + pad)
    min_samples = int(rate * _SILENCE_MIN_MS / 1000) * channels
    if end - start < min_samples:
        extra = min_samples - (end - start)
        start = max(0, start - extra)
        end = min(sample_count, start + min_samples)
    clipped = frames[start * width : end * width]
    if len(clipped) >= len(frames):
        return audio_bytes
    return speech_gateway.pcm_to_wav(clipped, sample_rate=rate, channels=channels)


def _pop_live_talk_wav_clips(buffer: bytearray, *, first: bool, flush: bool) -> list[bytes]:
    clips: list[bytes] = []
    need = _LIVE_TALK_FIRST_CLIP_PCM if first else _LIVE_TALK_CLIP_PCM
    while len(buffer) >= need:
        chunk = bytes(buffer[:need])
        del buffer[:need]
        clips.append(speech_gateway.pcm_to_wav(chunk))
        need = _LIVE_TALK_CLIP_PCM
    if flush and buffer:
        clips.append(speech_gateway.pcm_to_wav(bytes(buffer)))
        buffer.clear()
    return clips


def _spoken_reply_messages(
    user_text: str,
    history: list[tuple[str, str]] | None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": _SPOKEN_REPLY_SYSTEM}]
    for role, content in (history or [])[-_SPOKEN_REPLY_HISTORY:]:
        if role not in {"user", "assistant"}:
            continue
        text = " ".join((content or "").split()).strip()[:_SPOKEN_REPLY_TURN_CHARS]
        if not text:
            continue
        messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user_text})
    return messages


async def _iter_spoken_text_reply(
    settings: Settings,
    user_text: str,
    history: list[tuple[str, str]] | None,
) -> AsyncIterator[LiveTalkStreamEvent]:
    """Stream a short spoken reply. Do not wait for GPT Audio to finish."""
    assistant = ""
    async for token in stream_chat_completion(
        settings=settings,
        model_alias=auto_fast_alias(),
        messages=_spoken_reply_messages(user_text, history),
        max_tokens=_SPOKEN_REPLY_MAX_TOKENS,
    ):
        assistant += token
        stripped = assistant.strip()
        if stripped:
            yield LiveTalkStreamEvent(kind="assistant", text=stripped)
    if not assistant.strip():
        raise RuntimeError("live talk spoken reply was empty")


async def _iter_gpt_audio_reply(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str,
    history: list[tuple[str, str]] | None,
) -> AsyncIterator[LiveTalkStreamEvent]:
    model = resolve_live_talk_model(settings)
    pcm_buf = bytearray()
    first_clip = True
    assistant = ""
    async for pcm, text in speech_gateway.iter_speech_to_speech_via_openrouter(
        settings,
        audio_bytes,
        filename=filename,
        model=model,
        history=history,
    ):
        if text and text != assistant:
            assistant = text
            yield LiveTalkStreamEvent(kind="assistant", text=assistant.strip())
        if pcm:
            pcm_buf.extend(pcm)
            clips = _pop_live_talk_wav_clips(pcm_buf, first=first_clip, flush=False)
            if clips:
                first_clip = False
            for clip in clips:
                yield LiveTalkStreamEvent(kind="audio", audio_wav=clip)
    for clip in _pop_live_talk_wav_clips(pcm_buf, first=first_clip, flush=True):
        yield LiveTalkStreamEvent(kind="audio", audio_wav=clip)


async def iter_speech_to_speech(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
    history: list[tuple[str, str]] | None = None,
) -> AsyncIterator[LiveTalkStreamEvent]:
    """Whisper the user, then a short spoken text reply (not a full GPT Audio wait)."""
    if not settings.speech_live_talk_enabled:
        return
    if not audio_bytes or len(audio_bytes) > SPEECH_MAX_AUDIO_BYTES:
        logger.warning(
            "Live talk rejected: payload size=%s",
            len(audio_bytes) if audio_bytes else 0,
        )
        return
    if mock_llm.should_mock_llm(settings) and not settings.openrouter_api_key:
        yield LiveTalkStreamEvent(kind="user", text="This is a mock transcription.")
        yield LiveTalkStreamEvent(
            kind="audio",
            audio_wav=speech_gateway.pcm_to_wav(b"\x00\x00" * 1200),
        )
        yield LiveTalkStreamEvent(kind="assistant", text="This is a mock spoken reply.")
        return
    if not settings.openrouter_api_key:
        return
    if speech_gateway.openai_input_audio_format(filename, audio_bytes) is None:
        logger.warning(
            "Live talk rejected unsupported audio container filename=%s",
            filename,
        )
        return

    audio_bytes = trim_wav_silence(audio_bytes)
    user_text = ""
    try:
        user_text = (
            (await transcribe_audio(settings, audio_bytes, filename=filename)) or ""
        ).strip()
    except Exception:
        logger.exception("Live talk user transcription failed")
    if user_text:
        yield LiveTalkStreamEvent(kind="user", text=user_text)
        try:
            async for event in _iter_spoken_text_reply(settings, user_text, history):
                yield event
            return
        except Exception:
            logger.exception("Live talk spoken text reply failed; falling back to STS")
    else:
        logger.info("Live talk Whisper empty; still running STS")

    async for event in _iter_gpt_audio_reply(
        settings,
        audio_bytes,
        filename=filename,
        history=history,
    ):
        yield event
