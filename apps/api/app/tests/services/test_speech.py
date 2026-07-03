"""Tests for app.services.speech."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.speech import _audio_format, transcribe_audio


@pytest.mark.asyncio
async def test_transcribe_returns_mock_when_mock_llm_enabled():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        speech_transcription_enabled=True,
    )
    with patch("app.services.speech.mock_llm.should_mock_llm", return_value=True):
        text = await transcribe_audio(settings, b"fake-audio")
    assert text == "This is a mock transcription."


@pytest.mark.asyncio
async def test_transcribe_disabled_returns_none():
    settings = Settings(speech_transcription_enabled=False)
    assert await transcribe_audio(settings, b"fake-audio") is None


@pytest.mark.asyncio
async def test_transcribe_empty_payload_returns_none():
    settings = Settings(mock_llm_enabled=True, speech_transcription_enabled=True)
    assert await transcribe_audio(settings, b"") is None


def test_audio_format_from_filename():
    assert _audio_format("speech.m4a") == "m4a"
    assert _audio_format("clip.wav") == "wav"


@pytest.mark.asyncio
async def test_transcribe_openrouter_json_api():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
    )
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "hello there"}

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.speech.httpx.AsyncClient", return_value=client):
        text = await transcribe_audio(settings, b"audio-bytes", filename="speech.m4a")

    assert text == "hello there"
    call = client.post.call_args
    assert call.args[0] == "https://openrouter.ai/api/v1/audio/transcriptions"
    body = call.kwargs["json"]
    assert body["model"] == "openai/whisper-1"
    assert body["input_audio"]["format"] == "m4a"
