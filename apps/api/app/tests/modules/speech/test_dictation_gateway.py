"""The OpenAI side of dictation: the live session's shape, and a language OpenAI refuses.

Amharic's ``am`` is a code neither OpenAI transcription endpoint takes (measured
2026-11-23: the realtime mint answers 400 "Invalid value: 'am'", the recorded upload 400
"Language code 'am' is not recognized"). The recorded path failed every Amharic dictation
with a 502; both now name the language in the prompt instead.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways import openai_speech_gateway, speech_gateway


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


def _input(session: dict) -> dict:
    return session["audio"]["input"]


def test_the_streaming_transcriber_takes_a_language_list_and_no_server_vad():
    session = openai_speech_gateway.transcription_session_config("gpt-live-transcribe", "pt-BR")

    assert session["type"] == "transcription"
    assert "model" not in session and "instructions" not in session  # nothing answers
    audio = _input(session)
    assert audio["transcription"]["model"] == "gpt-live-transcribe"
    assert audio["transcription"]["languages"] == ["pt"]
    assert "language" not in audio["transcription"]
    # The phone commits once, on stop; the model takes no server VAD.
    assert audio["turn_detection"] is None


def test_a_gpt_4o_transcriber_takes_one_language_and_closes_segments_at_pauses():
    session = openai_speech_gateway.transcription_session_config("openai/gpt-4o-transcribe", "fr")

    audio = _input(session)
    assert audio["transcription"]["model"] == "gpt-4o-transcribe"
    assert audio["transcription"]["language"] == "fr"
    assert audio["turn_detection"]["type"] == "server_vad"


@pytest.mark.asyncio
async def test_a_refused_language_is_minted_without_its_code_and_named_in_the_prompt(caplog):
    client = MagicMock()
    client.post = AsyncMock(
        side_effect=[
            _response(
                400,
                text="Invalid value: 'am'. param=session.audio.input.transcription.languages[0]",
            ),
            _response(200, {"value": "ek_d", "expires_at": 7}),
            _response(200, {"value": "ek_e", "expires_at": 8}),
        ]
    )
    settings = Settings(openai_api_key="sk-test")

    with patch("app.gateways.openai_speech_gateway.get_pooled_client", return_value=client):
        first = await openai_speech_gateway.create_transcription_client_secret(
            settings, model="gpt-live-transcribe", language="am", safety_identifier="h"
        )
        second = await openai_speech_gateway.create_transcription_client_secret(
            settings, model="gpt-live-transcribe", language="am", safety_identifier="h"
        )

    assert first is not None and first.value == "ek_d"
    assert second is not None and second.value == "ek_e"
    bodies = [call.kwargs["json"] for call in client.post.call_args_list]
    sent = [_input(body["session"])["transcription"] for body in bodies]
    assert sent[0]["languages"] == ["am"]
    # Remembered: the next take does not send the doomed code first.
    for transcription in sent[1:]:
        assert "languages" not in transcription
        assert "Amharic" in transcription["prompt"]
    # The secret only opens the one call, right after the mint.
    assert bodies[0]["expires_after"] == {"anchor": "created_at", "seconds": 60}
    assert "minting it without the language" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 500])
async def test_a_mint_failure_that_is_not_the_language_is_none(status):
    """A 400 for another reason (a bad override) keeps the language for everyone after."""
    client = MagicMock()
    client.post = AsyncMock(return_value=_response(status, text="Invalid value: 'model'."))

    with patch("app.gateways.openai_speech_gateway.get_pooled_client", return_value=client):
        result = await openai_speech_gateway.create_transcription_client_secret(
            Settings(openai_api_key="sk-test"),
            model="gpt-live-transcribe",
            language="am",
            safety_identifier="h",
        )

    assert result is None
    assert client.post.await_count == 1
    assert speech_gateway._REFUSED_LANGUAGES == set()


@pytest.mark.asyncio
async def test_no_key_mints_nothing():
    result = await openai_speech_gateway.create_transcription_client_secret(
        Settings(openai_api_key=""),
        model="gpt-live-transcribe",
        language="en",
        safety_identifier="h",
    )

    assert result is None


@pytest.mark.asyncio
async def test_the_recorded_path_names_a_refused_language_in_the_prompt():
    client = MagicMock()
    client.post = AsyncMock(
        side_effect=[
            _response(400, text='{"error": {"param": "language"}}'),
            _response(200, {"text": "ሰላም"}),
        ]
    )

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await speech_gateway.transcribe_via_openai(
            Settings(openai_api_key="sk-test"),
            b"audio",
            filename="a.m4a",
            model="openai/gpt-4o-mini-transcribe",
            language="am",
        )

    assert text == "ሰላም"
    first, second = (call.kwargs["data"] for call in client.post.call_args_list)
    assert first["language"] == "am"
    assert "language" not in second
    assert "Amharic" in second["prompt"]


@pytest.mark.asyncio
async def test_the_recorded_path_keeps_a_language_openai_takes():
    client = MagicMock()
    client.post = AsyncMock(return_value=_response(200, {"text": "hola"}))

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await speech_gateway.transcribe_via_openai(
            Settings(openai_api_key="sk-test"),
            b"audio",
            filename="a.m4a",
            model="gpt-4o-mini-transcribe",
            language="es",
        )

    assert text == "hola"
    assert client.post.await_count == 1
    assert client.post.call_args.kwargs["data"]["language"] == "es"


@pytest.mark.asyncio
async def test_a_mint_racing_another_still_retries_without_the_refused_language():
    """Two Amharic mints at once: the other one marked "am" refused while this one's own
    refused request was out, and this one gave up with a 502."""

    async def post(*_args: object, **kwargs: object) -> MagicMock:
        transcription = _input(kwargs["json"]["session"])["transcription"]  # type: ignore[index]
        if "languages" in transcription:
            speech_gateway._REFUSED_LANGUAGES.add("am")  # the other mint
            return _response(400, text="Invalid value: 'am'. param=...languages[0]")
        return _response(200, {"value": "ek_d", "expires_at": 7})

    client = MagicMock()
    client.post = AsyncMock(side_effect=post)

    with patch("app.gateways.openai_speech_gateway.get_pooled_client", return_value=client):
        result = await openai_speech_gateway.create_transcription_client_secret(
            Settings(openai_api_key="sk-test"),
            model="gpt-live-transcribe",
            language="am",
            safety_identifier="h",
        )

    assert result is not None and result.value == "ek_d"
    assert client.post.await_count == 2


def test_every_voice_path_names_a_language_one_of_them_saw_refused():
    """One memory: the recorded clip's refusal reaches live dictation and live talk."""
    speech_gateway.mark_stt_language_refused("am")

    dictation = _input(
        openai_speech_gateway.transcription_session_config("gpt-live-transcribe", "am")
    )
    live_talk = openai_speech_gateway.realtime_session_config(Settings(), "Recall", language="am")
    recorded = speech_gateway._transcription_payload("gpt-4o-mini-transcribe", "am")

    for transcription in (dictation["transcription"], _input(live_talk)["transcription"]):
        assert "language" not in transcription and "languages" not in transcription
        assert "Amharic" in transcription["prompt"]
    assert "language" not in recorded and "Amharic" in recorded["prompt"]
