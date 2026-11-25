"""The recorded clip's transcript, routed by the app's language.

Whisper Large V3 Turbo on OpenRouter takes English, Spanish, French, Portuguese, Russian
and Turkish; gpt-4o-transcribe on OpenAI takes Amharic; gpt-4o-mini-transcribe takes
Hindi, any other language, a clip with no language, and any clip the routes before it
failed (``speech.service.STT_ROUTES``). Live dictation has its own tests
(``test_dictation_gateway.py``).
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import time
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways import speech_gateway, transcription_gateway
from app.modules.speech import service as speech_service
from app.modules.speech.service import resolve_stt_model, stt_routes_for, transcribe_audio
from app.services.quota import spend

_WHISPER_CLIENT = "app.gateways.transcription_gateway.get_pooled_client"
_OPENAI_CLIENT = "app.gateways.speech_gateway.get_pooled_client"
_WHISPER_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"


def _settings(**overrides: object) -> Settings:
    return Settings.model_validate(
        {
            "mock_llm_enabled": False,
            "openrouter_api_key": "or-test",
            "openai_api_key": "sk-test",
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


@pytest.mark.parametrize(
    "language, aliases",
    [
        ("en-US", ["speech-stt-model", "speech-stt-openai-model"]),
        ("es", ["speech-stt-model", "speech-stt-openai-model"]),
        ("fr-FR", ["speech-stt-model", "speech-stt-openai-model"]),
        ("pt_BR", ["speech-stt-model", "speech-stt-openai-model"]),
        ("ru", ["speech-stt-model", "speech-stt-openai-model"]),
        ("tr", ["speech-stt-model", "speech-stt-openai-model"]),
        ("am", ["speech-stt-openai-large-model", "speech-stt-openai-model"]),
        ("am-ET", ["speech-stt-openai-large-model", "speech-stt-openai-model"]),
        ("hi-IN", ["speech-stt-openai-model"]),
        ("de", ["speech-stt-openai-model"]),
        (None, ["speech-stt-openai-model"]),
        ("", ["speech-stt-openai-model"]),
    ],
)
def test_a_clip_is_offered_to_the_transcribers_of_its_language(language, aliases):
    assert [route.alias for route in stt_routes_for(language)] == aliases


@pytest.mark.asyncio
async def test_a_whisper_language_posts_base64_json_to_openrouter():
    whisper = _client(_response(200, {"text": "hello there", "usage": {"seconds": 1.2}}))
    openai = _client()
    spent: list[float] = []

    with patch(_WHISPER_CLIENT, return_value=whisper), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(
            _settings(),
            b"audio-bytes",
            filename="speech.m4a",
            language="en-US",
            on_spend=spent.append,
        )

    assert text == "hello there"
    call = whisper.post.call_args
    assert call.args[0] == _WHISPER_URL
    assert call.kwargs["headers"]["Authorization"] == "Bearer or-test"
    body = call.kwargs["json"]
    assert body["model"] == "openai/whisper-large-v3-turbo"
    assert body["language"] == "en"
    assert body["input_audio"] == {
        "data": base64.b64encode(b"audio-bytes").decode("ascii"),
        "format": "m4a",
    }
    openai.post.assert_not_awaited()
    assert spent == [spend.STT_WHISPER_SPEND_USD]


@pytest.mark.asyncio
@pytest.mark.parametrize("language, code", [("hi-IN", "hi"), (None, None)])
async def test_hindi_or_no_language_goes_to_openai(language, code):
    whisper = _client()
    openai = _client(_response(200, {"text": "नमस्ते"}))
    spent: list[float] = []

    with patch(_WHISPER_CLIENT, return_value=whisper), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(
            _settings(), b"audio-bytes", language=language, on_spend=spent.append
        )

    assert text == "नमस्ते"
    whisper.post.assert_not_awaited()
    call = openai.post.call_args
    assert call.args[0] == _OPENAI_URL
    assert call.kwargs["data"]["model"] == "gpt-4o-mini-transcribe"
    assert call.kwargs["data"].get("language") == code
    assert spent == [spend.STT_OPENAI_SPEND_USD]


@pytest.mark.asyncio
async def test_amharic_goes_to_gpt_4o_transcribe_with_its_refused_code_named_in_the_prompt():
    openai = _client(
        _response(400, text="Language code 'am' is not recognized: param language"),
        _response(200, {"text": "ሰላም"}),
    )
    spent: list[float] = []

    with patch(_WHISPER_CLIENT, return_value=_client()), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(
            _settings(), b"audio-bytes", language="am-ET", on_spend=spent.append
        )

    assert text == "ሰላም"
    first, second = (call.kwargs["data"] for call in openai.post.call_args_list)
    assert first["model"] == second["model"] == "gpt-4o-transcribe"
    assert first["language"] == "am"
    assert "language" not in second and "Amharic" in second["prompt"]
    assert spent == [spend.STT_OPENAI_LARGE_SPEND_USD]


@pytest.mark.asyncio
async def test_a_gpt_4o_transcribe_failure_is_asked_of_mini():
    openai = _client(_response(500, text="down"), _response(200, {"text": "ሰላም"}))
    spent: list[float] = []

    with patch(_WHISPER_CLIENT, return_value=_client()), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(
            _settings(), b"audio-bytes", language="am", on_spend=spent.append
        )

    assert text == "ሰላም"
    models = [call.kwargs["data"]["model"] for call in openai.post.call_args_list]
    assert models == ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
    assert spent == [spend.STT_OPENAI_LARGE_SPEND_USD, spend.STT_OPENAI_SPEND_USD]


@pytest.mark.asyncio
async def test_a_whisper_failure_is_asked_of_openai_and_both_are_spent():
    whisper = _client(_response(502, text="upstream down"))
    openai = _client(_response(200, {"text": "hola"}))
    calls: list[str] = []
    spent: list[float] = []

    with patch(_WHISPER_CLIENT, return_value=whisper), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(
            _settings(),
            b"audio-bytes",
            language="es",
            on_call=lambda: calls.append("on_call"),
            on_spend=spent.append,
        )

    assert text == "hola"
    assert whisper.post.await_count == 1 and openai.post.await_count == 1
    assert openai.post.call_args.kwargs["data"]["language"] == "es"
    assert calls == ["on_call"]  # once, before the first provider
    assert spent == [spend.STT_WHISPER_SPEND_USD, spend.STT_OPENAI_SPEND_USD]


@pytest.mark.asyncio
async def test_whisper_silence_is_an_answer_not_a_failure():
    openai = _client()

    with (
        patch(_WHISPER_CLIENT, return_value=_client(_response(200, {"text": ""}))),
        patch(_OPENAI_CLIENT, return_value=openai),
    ):
        text = await transcribe_audio(_settings(), b"silence-m4a", language="en")

    assert text == ""
    openai.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_both_failing_is_none():
    with (
        patch(_WHISPER_CLIENT, return_value=_client(_response(502, text="down"))),
        patch(_OPENAI_CLIENT, return_value=_client(_response(500, text="down"))),
    ):
        assert await transcribe_audio(_settings(), b"audio-bytes", language="en") is None


@pytest.mark.asyncio
async def test_without_an_openrouter_key_a_whisper_language_goes_to_openai():
    whisper = _client()
    openai = _client(_response(200, {"text": "hello"}))

    with patch(_WHISPER_CLIENT, return_value=whisper), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(_settings(openrouter_api_key=""), b"audio", language="en")

    assert text == "hello"
    whisper.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_without_an_openai_key_hindi_asks_nobody():
    whisper, openai = _client(), _client()
    calls: list[str] = []

    with patch(_WHISPER_CLIENT, return_value=whisper), patch(_OPENAI_CLIENT, return_value=openai):
        text = await transcribe_audio(
            _settings(openai_api_key=""), b"audio", language="hi", on_call=lambda: calls.append("x")
        )

    assert text is None
    assert calls == []
    whisper.post.assert_not_awaited()
    openai.post.assert_not_awaited()


@pytest.mark.parametrize(
    "override, alias, model",
    [
        ("", "speech-stt-model", "openai/whisper-large-v3-turbo"),
        ("openai/whisper-large-v3", "speech-stt-model", "openai/whisper-large-v3"),
        ("openai/whisper-1", "speech-stt-model", "openai/whisper-1"),
        # The values of old (OpenAI-direct names, the old .env.example's suggestion) and
        # any other model are not OpenRouter Whispers: the catalog's model is used.
        ("gpt-4o-mini-transcribe", "speech-stt-model", "openai/whisper-large-v3-turbo"),
        ("openai/gpt-4o-mini-transcribe", "speech-stt-model", "openai/whisper-large-v3-turbo"),
        ("google/gemini-3.5-transcribe", "speech-stt-model", "openai/whisper-large-v3-turbo"),
        # The override is Whisper's; OpenAI's route keeps its catalog model.
        ("openai/whisper-large-v3", "speech-stt-openai-model", "openai/gpt-4o-mini-transcribe"),
    ],
)
def test_the_override_is_whispers_and_only_an_openrouter_whisper(override, alias, model):
    assert resolve_stt_model(_settings(speech_transcription_model=override), alias) == model


def _short_deadline(deadline: float, try_seconds: float) -> object:
    """The route loop with a ``deadline`` and every capped try held to ``try_seconds``."""
    routes = tuple(
        dataclasses.replace(route, try_seconds=try_seconds) if route.try_seconds else route
        for route in speech_service.STT_ROUTES
    )
    return patch.multiple(speech_service, STT_ROUTES=routes, STT_DEADLINE_SECONDS=deadline)


async def _hang(*_args: object, **_kwargs: object) -> str | None:
    await asyncio.sleep(60)
    return "never"


@pytest.mark.asyncio
async def test_a_hanging_whisper_host_still_leaves_openai_time():
    openai = AsyncMock(return_value="hello")
    spent: list[float] = []

    with (
        _short_deadline(deadline=1.0, try_seconds=0.05),
        patch.object(transcription_gateway, "transcribe_via_openrouter", _hang),
        patch.object(speech_gateway, "transcribe_via_openai", openai),
    ):
        started = time.monotonic()
        text = await transcribe_audio(_settings(), b"audio", language="en", on_spend=spent.append)

    assert text == "hello"
    assert time.monotonic() - started < 0.5
    assert spent == [spend.STT_WHISPER_SPEND_USD, spend.STT_OPENAI_SPEND_USD]


@pytest.mark.asyncio
async def test_every_try_ends_by_the_shared_deadline():
    with (
        _short_deadline(deadline=0.2, try_seconds=0.15),
        patch.object(transcription_gateway, "transcribe_via_openrouter", _hang),
        patch.object(speech_gateway, "transcribe_via_openai", _hang),
    ):
        started = time.monotonic()
        text = await transcribe_audio(_settings(), b"audio", language="en")

    assert text is None
    assert time.monotonic() - started < 0.4


def test_the_real_tries_fit_under_the_phones_wait():
    """The phone stops waiting at 25 s; each route's cap leaves the fallback some time."""
    assert speech_service.STT_DEADLINE_SECONDS < 25
    for route in speech_service.STT_ROUTES:
        if route.try_seconds is not None:
            assert route.try_seconds <= speech_service.STT_DEADLINE_SECONDS - 5


def _post_clip(language: str) -> tuple[int, AsyncMock]:
    import fakeredis.aioredis
    from fastapi.testclient import TestClient

    from app.core.deps import get_settings_dep
    from app.tests.api_support import api_user, app_with_user

    app = app_with_user(api_user(plan="pro"))
    app.dependency_overrides[get_settings_dep] = lambda: _settings()
    record = AsyncMock()
    with (
        patch(
            "app.modules.speech.api.get_redis_client",
            return_value=fakeredis.aioredis.FakeRedis(decode_responses=True),
        ),
        patch("app.modules.speech.api.quota_service.record_voice_spend", record),
    ):
        response = TestClient(app).post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            json={"audio_base64": base64.b64encode(b"audio").decode(), "language": language},
        )
    return response.status_code, record


def test_the_endpoint_records_both_estimates_when_both_fail():
    with (
        patch.object(
            transcription_gateway, "transcribe_via_openrouter", AsyncMock(return_value=None)
        ),
        patch.object(speech_gateway, "transcribe_via_openai", AsyncMock(return_value=None)),
    ):
        status, record = _post_clip("es")

    assert status == 502
    record.assert_awaited_once()
    assert record.await_args.args[1] == pytest.approx(
        spend.STT_WHISPER_SPEND_USD + spend.STT_OPENAI_SPEND_USD
    )


def test_the_endpoint_records_only_the_route_that_answered():
    with (
        patch.object(
            transcription_gateway, "transcribe_via_openrouter", AsyncMock(return_value="hola")
        ),
        patch.object(speech_gateway, "transcribe_via_openai", AsyncMock(return_value="x")),
    ):
        status, record = _post_clip("es")

    assert status == 200
    assert record.await_args.args[1] == pytest.approx(spend.STT_WHISPER_SPEND_USD)


@pytest.mark.asyncio
async def test_a_code_live_dictation_saw_refused_still_goes_to_whisper():
    """The refused-language memory is OpenAI's; Whisper takes every code it routes."""
    speech_gateway.mark_stt_language_refused("es")
    client = _client(_response(200, {"text": "hola"}))

    with patch(_WHISPER_CLIENT, return_value=client):
        text = await transcription_gateway.transcribe_via_openrouter(
            _settings(),
            b"audio",
            filename="a.m4a",
            model="openai/whisper-large-v3-turbo",
            language="es",
        )

    assert text == "hola"
    body = client.post.call_args.kwargs["json"]
    assert body["language"] == "es" and "prompt" not in body


@pytest.mark.asyncio
async def test_a_refused_language_is_dropped_once_and_detected():
    client = _client(
        _response(400, text='{"error": {"message": "Unsupported language: xx"}}'),
        _response(200, {"text": "bonjour"}),
    )

    with patch(_WHISPER_CLIENT, return_value=client):
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

    with patch(_WHISPER_CLIENT, return_value=client):
        text = await transcription_gateway.transcribe_via_openrouter(
            _settings(), b"audio", filename="a.m4a", model="m/x", language="en"
        )

    assert text is None
    assert client.post.await_count == 1


def test_every_route_names_a_catalog_alias_and_the_last_takes_any_language():
    for route in speech_service.STT_ROUTES:
        assert speech_service.model_catalog.get(route.alias)
    assert speech_service.STT_ROUTES[-1].languages is None
