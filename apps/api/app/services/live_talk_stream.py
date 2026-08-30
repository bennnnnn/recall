"""Stream live-talk audio clips + transcripts (Whisper in parallel with GPT Audio)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.gateways import mock_llm, speech_gateway
from app.models.schemas.integrations import SPEECH_MAX_AUDIO_BYTES
from app.services.speech import (
    resolve_live_talk_model,
    transcribe_audio,
)

logger = logging.getLogger(__name__)

# 24 kHz 16-bit mono. First clip is short so playback can start before the full reply.
_LIVE_TALK_FIRST_CLIP_PCM = 24000 * 2 * 7 // 20  # 0.35s
_LIVE_TALK_CLIP_PCM = 24000 * 2 * 3 // 4  # 0.75s


@dataclass(frozen=True, slots=True)
class LiveTalkStreamEvent:
    kind: Literal["user", "assistant", "audio"]
    text: str = ""
    audio_wav: bytes = b""


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


async def iter_speech_to_speech(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
    history: list[tuple[str, str]] | None = None,
) -> AsyncIterator[LiveTalkStreamEvent]:
    """Stream spoken clips + transcripts. Whisper for the user runs in parallel."""
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

    whisper_task = asyncio.create_task(transcribe_audio(settings, audio_bytes, filename=filename))
    model = resolve_live_talk_model(settings)
    pcm_buf = bytearray()
    first_clip = True
    assistant = ""
    user_emitted = False
    try:
        async for pcm, text in speech_gateway.iter_speech_to_speech_via_openrouter(
            settings,
            audio_bytes,
            filename=filename,
            model=model,
            history=history,
        ):
            if not user_emitted and whisper_task.done():
                user_emitted = True
                try:
                    user_text = (whisper_task.result() or "").strip()
                except Exception:
                    logger.exception("Live talk user transcription failed")
                    user_text = ""
                if user_text:
                    yield LiveTalkStreamEvent(kind="user", text=user_text)
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
        if not user_emitted:
            try:
                user_text = ((await whisper_task) or "").strip()
            except Exception:
                logger.exception("Live talk user transcription failed")
                user_text = ""
            if user_text:
                yield LiveTalkStreamEvent(kind="user", text=user_text)
    finally:
        if not whisper_task.done():
            whisper_task.cancel()
            try:
                await whisper_task
            except asyncio.CancelledError:
                logger.debug("Cancelled in-flight live-talk transcription")
