import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.gateways import openai_speech_gateway
from app.gateways.openai_speech_gateway import RealtimeCallResult, RealtimeClientSecretResult
from app.main import create_app
from app.routers.speech_realtime import _realtime_instructions
from app.tests.test_routers import _fake_user


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
async def test_realtime_call_uses_semantic_vad_and_server_key():
    response = MagicMock()
    response.status_code = 200
    response.text = "v=0\r\nanswer"
    response.headers = {"location": "/v1/realtime/calls/call_123"}
    response.raise_for_status = MagicMock()
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    settings = Settings(
        openai_api_key="sk-test",
        speech_realtime_voice_enabled=True,
        openai_realtime_model="gpt-realtime-2.1",
    )

    with patch("app.gateways.openai_speech_gateway.get_pooled_client", return_value=client):
        result = await openai_speech_gateway.create_realtime_call(
            settings,
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


@pytest.mark.asyncio
async def test_realtime_client_secret_binds_session_config_and_retries_connects():
    response = MagicMock()
    response.status_code = 200
    response.text = '{"value":"ek_test","expires_at":123}'
    response.raise_for_status = MagicMock()
    response.json.return_value = {"value": "ek_test", "expires_at": 123}
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    settings = Settings(
        openai_api_key="sk-test",
        speech_realtime_voice_enabled=True,
        openai_realtime_model="gpt-realtime-2.1",
    )

    with patch(
        "app.gateways.openai_speech_gateway.get_pooled_client", return_value=client
    ) as pooled:
        result = await openai_speech_gateway.create_realtime_client_secret(
            settings,
            instructions="be concise",
            safety_identifier="user-hash",
        )

    assert result == RealtimeClientSecretResult(value="ek_test", expires_at=123)
    pooled.assert_called_once_with(10.0, connect_retries=2)
    call = client.post.call_args
    assert call.kwargs["headers"]["Authorization"] == "Bearer sk-test"
    assert call.kwargs["headers"]["OpenAI-Safety-Identifier"] == "user-hash"
    assert call.kwargs["json"]["session"]["model"] == "gpt-realtime-2.1"
    assert call.kwargs["json"]["session"]["output_modalities"] == ["audio"]


def _realtime_app(user, settings: Settings):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings
    return app


def test_persist_requires_issued_realtime_session():
    user = _fake_user(plan="pro")
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(_realtime_app(user, settings))
    with patch("app.routers.speech_realtime.get_redis_client", return_value=fake_redis):
        r = client.post(
            "/speech/live/persist",
            headers={"Authorization": "Bearer tok"},
            json={
                "chat_id": str(uuid4()),
                "call_id": "not-a-real-session",
                "user_text": "hello",
                "assistant_text": "hi",
            },
        )
    assert r.status_code == 403


def test_realtime_session_returns_ephemeral_key_and_recall_session_id():
    user = _fake_user(plan="pro")
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
        speech_rate_limit_per_minute=0,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(_realtime_app(user, settings))
    with (
        patch("app.routers.speech_realtime.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech_realtime.quota_service.live_talk_limit_for_user",
            return_value=30,
        ),
        patch(
            "app.routers.speech_realtime.quota_service.reserve_live_talk",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.routers.speech_realtime.quota_service.clear_live_talk_pending",
            AsyncMock(),
        ),
        patch(
            "app.routers.speech_realtime.openai_speech_gateway.create_realtime_client_secret",
            AsyncMock(return_value=RealtimeClientSecretResult(value="ek_test", expires_at=123)),
        ),
    ):
        r = client.post(
            "/speech/live/session",
            headers={"Authorization": "Bearer tok"},
            json={},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["client_secret"] == "ek_test"
    assert body["expires_at"] == 123
    assert body["call_id"]
    assert body["model"] == "gpt-realtime-2.1"


def test_legacy_webrtc_endpoint_requires_current_mobile_bundle():
    user = _fake_user(plan="pro")
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
    )
    client = TestClient(_realtime_app(user, settings))
    r = client.post(
        "/speech/live/webrtc",
        headers={"Authorization": "Bearer tok"},
        json={"sdp": "v=0\r\n" + "o=recall 1 1 IN IP4 127.0.0.1\r\n"},
    )
    assert r.status_code == 426
    assert "Legacy Live Talk client detected" in r.json()["detail"]
