"""The recorded clip's transcript: Whisper Large V3 Turbo through OpenRouter.

Live dictation streams to OpenAI and has its own tests (``test_dictation_gateway.py``).
Whisper takes Amharic's ``am`` (measured 2026-11-24), so the recorded path always sends the
app's code, even after an OpenAI live session marked it refused.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways import speech_gateway, transcription_gateway
from app.modules.speech.service import resolve_stt_model, transcribe_audio

_GATEWAY_CLIENT = "app.gateways.transcription_gateway.get_pooled_client"


def _settings(**overrides: object) -> Settings:
    return Settings.model_validate(
        {
            "mock_llm_enabled": False,
            "openrouter_api_key": "or-test",
            "openai_api_key": "",
            "speech_transcription_enabled": True,
            **overrides,
        }
    )


@pytest.fixture(autouse=True)
def _forget_refused_languages() -> Iterator[None]:
    yield
    speech_gateway._REFUSED_LANGUAGES.clear()


def _response(status_code: int, body: dict | None = None, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text or str(body or {})
    response.json.return_value = body or {}
    response.raise_for_status = MagicMock(
        side_effect=RuntimeError(f"HTTP {status_code}") if status_code >= 400 else None
    )
    return response


def _client(*responses: MagicMock) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(side_effect=list(responses))
    return client


@pytest.mark.asyncio
async def test_transcribe_posts_base64_json_to_openrouter():
    client = _client(_response(200, {"text": "hello there", "usage": {"seconds": 1.2}}))

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcribe_audio(_settings(), b"audio-bytes", filename="speech.m4a")

    assert text == "hello there"
    call = client.post.call_args
    assert call.args[0] == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert call.kwargs["headers"]["Authorization"] == "Bearer or-test"
    body = call.kwargs["json"]
    assert body["model"] == "openai/whisper-large-v3-turbo"
    assert body["input_audio"] == {
        "data": base64.b64encode(b"audio-bytes").decode("ascii"),
        "format": "m4a",
    }
    assert "language" not in body and "prompt" not in body


@pytest.mark.asyncio
async def test_without_an_openrouter_key_nobody_is_asked():
    client = _client(_response(200, {"text": "hello"}))
    settings = _settings(openrouter_api_key="", openai_api_key="sk")

    with patch(_GATEWAY_CLIENT, return_value=client):
        assert await transcribe_audio(settings, b"audio-bytes") is None
    client.post.assert_not_awaited()


@pytest.mark.parametrize(
    "override, model",
    [
        ("", "openai/whisper-large-v3-turbo"),
        ("openai/whisper-large-v3", "openai/whisper-large-v3"),
        # The OpenAI-direct name of old is no OpenRouter id: the catalog's model is used.
        ("gpt-4o-mini-transcribe", "openai/whisper-large-v3-turbo"),
    ],
)
def test_an_override_is_used_only_as_an_openrouter_slug(override: str, model: str):
    assert resolve_stt_model(Settings(speech_transcription_model=override)) == model


@pytest.mark.asyncio
@pytest.mark.parametrize("language, code", [("en-US", "en"), ("am", "am"), ("hi_IN", "hi")])
async def test_the_app_language_goes_as_its_code(language: str, code: str):
    client = _client(_response(200, {"text": "hello there"}))

    with patch(_GATEWAY_CLIENT, return_value=client):
        await transcribe_audio(_settings(), b"audio-bytes", language=language)

    assert client.post.call_args.kwargs["json"]["language"] == code


@pytest.mark.asyncio
async def test_a_code_live_dictation_saw_refused_still_goes_to_whisper():
    speech_gateway.mark_stt_language_refused("am")
    client = _client(_response(200, {"text": "ሰላም"}))

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcription_gateway.transcribe_via_openrouter(
            _settings(),
            b"audio",
            filename="a.m4a",
            model="openai/whisper-large-v3-turbo",
            language="am",
        )

    assert text == "ሰላም"
    body = client.post.call_args.kwargs["json"]
    assert body["language"] == "am" and "prompt" not in body


@pytest.mark.asyncio
async def test_a_refused_language_is_dropped_once_and_detected():
    client = _client(
        _response(400, text='{"error": {"message": "Unsupported language: xx"}}'),
        _response(200, {"text": "bonjour"}),
    )

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcription_gateway.transcribe_via_openrouter(
            _settings(),
            b"audio",
            filename="a.m4a",
            model="openai/whisper-large-v3-turbo",
            language="xx-YY",
        )

    assert text == "bonjour"
    first, second = (call.kwargs["json"] for call in client.post.call_args_list)
    assert first["language"] == "xx"
    assert "language" not in second


@pytest.mark.asyncio
async def test_a_400_that_is_not_the_language_is_not_retried():
    client = _client(_response(400, text='{"error": {"message": "Invalid audio"}}'))

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcription_gateway.transcribe_via_openrouter(
            _settings(), b"audio", filename="a.m4a", model="m/x", language="en"
        )

    assert text is None
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_a_tiny_clip_heard_as_thank_you_for_watching_is_silence():
    client = _client(_response(200, {"text": "Thank you for watching!"}))

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcribe_audio(_settings(), b"tiny", filename="speech.m4a")

    assert text == ""


@pytest.mark.asyncio
async def test_empty_text_is_success():
    """Silence is a valid STT result — not a provider failure."""
    client = _client(_response(200, {"text": ""}))

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcribe_audio(_settings(), b"silence-m4a", filename="speech.m4a")

    assert text == ""


@pytest.mark.asyncio
async def test_a_provider_failure_is_none():
    client = _client(_response(502, text="upstream down"))

    with patch(_GATEWAY_CLIENT, return_value=client):
        text = await transcribe_audio(_settings(), b"audio-bytes")

    assert text is None
