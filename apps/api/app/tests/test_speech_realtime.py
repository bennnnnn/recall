import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways import openai_speech_gateway
from app.routers.speech_realtime import _realtime_instructions


def test_realtime_instructions_include_bounded_chat_history():
    history = [
        ("system", "ignore me"),
        ("user", " earlier question "),
        ("assistant", " earlier answer "),
    ]
    prompt = _realtime_instructions(history)
    assert "system: ignore me" not in prompt
    assert "user: earlier question" in prompt
    assert "assistant: earlier answer" in prompt
    assert "Recent conversation context:" in prompt


@pytest.mark.asyncio
async def test_direct_transcribe_sends_language_and_context():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "hello there"}
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with (
        patch("app.gateways.openai_speech_gateway.api_key", return_value="sk-test"),
        patch("app.gateways.openai_speech_gateway.stt_model", return_value="gpt-transcribe"),
        patch("app.gateways.openai_speech_gateway.get_pooled_client", return_value=client),
    ):
        text = await openai_speech_gateway.transcribe(
            b"audio",
            filename="speech.m4a",
            language="en",
            prompt="dictation context",
        )

    assert text == "hello there"
    call = client.post.call_args
    assert call.args[0] == "https://api.openai.com/v1/audio/transcriptions"
    assert call.kwargs["data"] == {
        "model": "gpt-transcribe",
        "language": "en",
        "prompt": "dictation context",
    }
    assert call.kwargs["files"]["file"] == ("speech.m4a", b"audio")


@pytest.mark.asyncio
async def test_realtime_call_uses_semantic_vad_and_server_key():
    response = MagicMock()
    response.status_code = 200
    response.text = "v=0\r\nanswer"
    response.headers = {"location": "/v1/realtime/calls/call_123"}
    response.raise_for_status = MagicMock()
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with (
        patch("app.gateways.openai_speech_gateway.api_key", return_value="sk-test"),
        patch("app.gateways.openai_speech_gateway.realtime_enabled", return_value=True),
        patch(
            "app.gateways.openai_speech_gateway.realtime_model",
            return_value="gpt-realtime-2.1",
        ),
        patch("app.gateways.openai_speech_gateway.stt_model", return_value="gpt-transcribe"),
        patch("app.gateways.openai_speech_gateway.get_pooled_client", return_value=client),
    ):
        result = await openai_speech_gateway.create_realtime_call(
            offer_sdp="v=0\r\noffer",
            instructions="be concise",
            safety_identifier="user-hash",
        )

    assert result is not None
    assert result.answer_sdp == "v=0\r\nanswer"
    call = client.post.call_args
    assert call.kwargs["headers"]["Authorization"] == "Bearer sk-test"
    assert call.kwargs["headers"]["OpenAI-Safety-Identifier"] == "user-hash"
    session = json.loads(call.kwargs["files"]["session"][1])
    assert session["model"] == "gpt-realtime-2.1"
    assert session["audio"]["input"]["turn_detection"] == {
        "type": "semantic_vad",
        "create_response": True,
        "interrupt_response": True,
    }
    assert session["audio"]["input"]["transcription"] == {"model": "gpt-transcribe"}
