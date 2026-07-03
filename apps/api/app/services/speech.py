"""Speech-to-text via OpenRouter (Whisper)."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.core.config import Settings
from app.gateways import mock_llm

logger = logging.getLogger(__name__)

_MAX_BYTES = 5_000_000
_OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_WHISPER_MODEL = "openai/whisper-1"
_TRANSCRIBE_TIMEOUT = 60.0

_FORMAT_BY_SUFFIX: dict[str, str] = {
    ".m4a": "m4a",
    ".mp3": "mp3",
    ".mp4": "mp4",
    ".wav": "wav",
    ".webm": "webm",
    ".flac": "flac",
}


def _audio_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return _FORMAT_BY_SUFFIX.get(suffix, suffix.lstrip(".") or "m4a")


async def transcribe_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "speech.m4a",
) -> str | None:
    if not settings.speech_transcription_enabled:
        return None
    if not audio_bytes or len(audio_bytes) > _MAX_BYTES:
        return None
    if mock_llm.should_mock_llm(settings):
        return "This is a mock transcription."
    if not settings.openrouter_api_key:
        return None

    payload = {
        "model": _WHISPER_MODEL,
        "input_audio": {
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "format": _audio_format(filename),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=_TRANSCRIBE_TIMEOUT) as client:
            response = await client.post(
                _OPENROUTER_TRANSCRIBE_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        text = str(data.get("text") or "").strip()
        return text or None
    except Exception:
        logger.exception("Speech transcription failed")
        return None
