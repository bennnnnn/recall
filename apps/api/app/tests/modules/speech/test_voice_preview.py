"""Settings → Voice: the voice picked says its name, through the engine that will speak it."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.main import create_app
from app.modules.speech import voice_preview
from app.modules.speech.voice_preview import UnknownVoiceError, preview_engine, preview_line
from app.tests.api_support import api_user

_KOKORO = "app.gateways.openrouter_speech_gateway.synthesize_via_openrouter"
_OPENAI = "app.gateways.speech_gateway.synthesize_via_openai"


def _last(mock: AsyncMock) -> Any:
    call = mock.await_args
    assert call is not None
    return call


def _settings(**kw: Any) -> Settings:
    return Settings(
        openai_api_key="sk-test", openrouter_api_key="or-test", mock_llm_enabled=False, **kw
    )


@pytest.mark.parametrize(
    "kind, voice, language, alias",
    [
        ("reply", "af_heart", "en", "speech-tts-kokoro-model"),
        ("reply", "ef_dora", "es", "speech-tts-kokoro-model"),
        ("reply", "coral", "ru", "speech-tts-model"),
        ("live", "marin", "en", "speech-voice-preview-model"),
        ("live", "verse", "am", "speech-voice-preview-model"),
    ],
)
def test_each_voice_is_previewed_by_the_engine_that_speaks_it(
    kind: Any, voice: str, language: str, alias: str
) -> None:
    assert preview_engine(kind, voice, language) == alias


@pytest.mark.parametrize(
    "kind, voice, language",
    [
        ("reply", "coral", "en"),  # English replies play in Kokoro's voices
        ("reply", "af_heart", "ru"),  # Russian ones in tts-1's
        ("reply", "marin", "en"),
        ("live", "af_heart", "en"),
        ("live", "onyx", "en"),  # tts-1 has it; live talk does not
    ],
)
def test_a_voice_the_engine_lacks_is_refused(kind: Any, voice: str, language: str) -> None:
    with pytest.raises(UnknownVoiceError):
        preview_engine(kind, voice, language)


def test_the_line_names_the_voice_in_the_app_language() -> None:
    assert preview_line("af_heart", "en") == "Hi, I'm Heart."
    assert preview_line("em_alex", "es") == "Hola, soy Alex."
    assert preview_line("cedar", "fr") == "Bonjour, je suis Cedar."
    assert preview_line("marin", "xx") == "Hi, I'm Marin."


@pytest.mark.asyncio
async def test_a_reply_voice_is_made_once_by_kokoro_then_kept() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    kokoro = AsyncMock(return_value=(b"ID3heart", "audio/mpeg"))
    spent: list[float] = []
    with patch(_KOKORO, kokoro), patch(_OPENAI, AsyncMock()) as openai:
        for _ in range(2):
            clip = await voice_preview.voice_preview(
                _settings(), redis, kind="reply", voice="af_heart", language="en",
                on_spend=spent.append,
            )  # fmt: skip
            assert clip == (b"ID3heart", "audio/mpeg")
    kokoro.assert_awaited_once()
    assert _last(kokoro).args[1] == "Hi, I'm Heart."
    assert _last(kokoro).kwargs == {"model": "hexgrad/kokoro-82m", "voice": "af_heart"}
    openai.assert_not_awaited()
    assert spent == [pytest.approx(len("Hi, I'm Heart.") * 4.0 / 1_000_000)]


@pytest.mark.asyncio
async def test_a_failed_kokoro_preview_plays_no_other_voice() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch(_KOKORO, AsyncMock(return_value=None)), patch(_OPENAI, AsyncMock()) as openai:
        clip = await voice_preview.voice_preview(
            _settings(), redis, kind="reply", voice="bm_george", language="en"
        )
    assert clip is None
    openai.assert_not_awaited()  # tts-1 would say it in ash: not the voice picked
    assert await redis.keys("speech_preview:*") == []


@pytest.mark.asyncio
async def test_a_live_talk_voice_is_spoken_by_gpt_4o_mini_tts_in_the_app_language() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    openai = AsyncMock(return_value=(b"ID3marin", "audio/mpeg"))
    with patch(_OPENAI, openai), patch(_KOKORO, AsyncMock()) as kokoro:
        clip = await voice_preview.voice_preview(
            _settings(), redis, kind="live", voice="marin", language="es"
        )
    assert clip == (b"ID3marin", "audio/mpeg")
    kokoro.assert_not_awaited()
    assert _last(openai).args[1] == "Hola, soy Marin."
    assert _last(openai).kwargs["model"] == "openai/gpt-4o-mini-tts"
    assert _last(openai).kwargs["voice"] == "marin"


@pytest.mark.asyncio
async def test_a_kept_clip_is_per_language() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    openai = AsyncMock(return_value=(b"ID3", "audio/mpeg"))
    with patch(_OPENAI, openai):
        for language in ("en", "fr", "en"):
            await voice_preview.voice_preview(
                _settings(), redis, kind="live", voice="cedar", language=language
            )
    assert openai.await_count == 2


def _client(user: Any, **settings: Any) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: _settings(**settings)
    return TestClient(app)


def _post(client: TestClient, **body: str) -> Any:
    return client.post("/speech/voice-preview", headers={"Authorization": "Bearer tok"}, json=body)


def test_the_endpoint_answers_mp3_and_takes_no_listen_tokens() -> None:
    client = _client(api_user(plan="pro", locale="en"))
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    spend = AsyncMock()
    tokens = AsyncMock()
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=redis),
        patch(_KOKORO, AsyncMock(return_value=(b"ID3heart", "audio/mpeg"))),
        patch("app.modules.speech.api.quota_service.record_voice_spend", spend),
        patch("app.modules.speech.api.charge_tts_tokens", tokens),
    ):
        first = _post(client, voice="af_heart", kind="reply")
        again = _post(client, voice="af_heart", kind="reply")
    assert first.status_code == again.status_code == 200
    assert base64.b64decode(first.json()["audio_base64"]) == b"ID3heart"
    assert first.json()["content_type"] == "audio/mpeg"
    tokens.assert_not_awaited()
    spend.assert_awaited_once()  # the kept clip costs nothing


@pytest.mark.parametrize(
    "plan, body, status",
    [
        ("pro", {"voice": "coral", "kind": "reply"}, 422),  # not an English reply voice
        ("pro", {"voice": "af_heart", "kind": "live"}, 422),
        ("pro", {"voice": "marin", "kind": "other"}, 422),
        ("free", {"voice": "af_heart", "kind": "reply"}, 403),
        ("free", {"voice": "marin", "kind": "live"}, 403),
    ],
)
def test_the_endpoint_refuses_what_it_cannot_say_truthfully(
    plan: str, body: dict[str, str], status: int
) -> None:
    client = _client(api_user(plan=plan, locale="en"))
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=redis),
        patch(_KOKORO, AsyncMock(return_value=(b"ID3", "audio/mpeg"))) as kokoro,
        patch(_OPENAI, AsyncMock(return_value=(b"ID3", "audio/mpeg"))) as openai,
    ):
        assert _post(client, **body).status_code == status
    kokoro.assert_not_awaited()
    openai.assert_not_awaited()


def test_the_endpoint_is_rate_limited() -> None:
    client = _client(api_user(plan="pro", locale="en"), speech_rate_limit_per_minute=2)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=redis),
        patch(_OPENAI, AsyncMock(return_value=(b"ID3", "audio/mpeg"))),
    ):
        codes = [_post(client, voice="cedar", kind="live").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_a_failed_preview_is_a_502() -> None:
    client = _client(api_user(plan="pro", locale="en"))
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=redis),
        patch(_KOKORO, AsyncMock(return_value=None)),
    ):
        assert _post(client, voice="af_heart", kind="reply").status_code == 502
