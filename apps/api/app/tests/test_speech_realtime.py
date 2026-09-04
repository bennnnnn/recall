from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.gateways import openai_speech_gateway
from app.gateways.openai_speech_gateway import RealtimeClientSecretResult
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
    assert "UNTRUSTED CONTENT — memory" not in prompt


def test_realtime_instructions_include_memory_block():
    prompt = _realtime_instructions(None, memory_block="Allergic to peanuts")
    assert "[BEGIN UNTRUSTED CONTENT — memory]" in prompt
    assert "Allergic to peanuts" in prompt
    assert "user-saved notes" in prompt
    assert "do not recite them back" in prompt


def test_realtime_instructions_omit_empty_memory():
    prompt = _realtime_instructions(None, memory_block="   ")
    assert "UNTRUSTED CONTENT — memory" not in prompt


def test_realtime_instructions_include_custom_instructions():
    from app.services.live_talk import voice_custom_instructions

    wrapped = voice_custom_instructions(_fake_user(custom_instructions="Keep answers short."))
    prompt = _realtime_instructions(None, custom_instructions=wrapped)
    assert "[BEGIN USER PREFERENCES]" in prompt
    assert "Keep answers short." in prompt


def test_physical_phone_session_supports_barge_in_and_only_read_only_tools():
    config = openai_speech_gateway.realtime_session_config(
        Settings(), "Recall", barge_in=True, tools_enabled=True
    )
    assert config["audio"]["input"]["turn_detection"]["interrupt_response"] is True
    assert {tool["name"] for tool in config["tools"]} == {"memory_lookup", "web_search"}


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
    session = call.kwargs["json"]["session"]
    assert session["model"] == "gpt-realtime-2.1"
    assert session["output_modalities"] == ["audio"]
    assert "include" not in session
    assert session["audio"]["input"]["noise_reduction"] == {"type": "near_field"}
    assert session["audio"]["input"]["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
        "create_response": False,
        "interrupt_response": False,
    }
    transcription = session["audio"]["input"]["transcription"]
    assert transcription["model"] == "gpt-live-transcribe"
    assert "Do not invent speech from silence" in transcription["prompt"]


def _realtime_app(user, settings: Settings):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings
    return app


@contextmanager
def _session_mint_patches(*, mint: AsyncMock, memory_block: str = ""):
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
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
            "app.routers.speech_realtime.live_talk_service.load_live_talk_session_context",
            AsyncMock(return_value=(None, memory_block)),
        ),
        patch(
            "app.routers.speech_realtime.openai_speech_gateway.create_realtime_client_secret",
            mint,
        ),
    ):
        yield


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


def test_persist_ignores_assistant_only_phantom_turn():
    user = _fake_user(plan="pro")
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
    )
    client = TestClient(_realtime_app(user, settings))
    with patch("app.routers.speech_realtime.get_redis_client") as redis_client:
        r = client.post(
            "/speech/live/persist",
            headers={"Authorization": "Bearer tok"},
            json={
                "chat_id": str(uuid4()),
                "call_id": "phantom-session",
                "user_text": "",
                "assistant_text": "Hi there. How can I help?",
            },
        )
    assert r.status_code == 204
    redis_client.assert_not_called()


def test_voice_sources_persist_in_the_canonical_chat_fence():
    import json

    user = _fake_user(plan="pro")
    client = TestClient(_realtime_app(user, Settings()))
    sources = [{"title": "Official score", "url": "https://example.com/score"}]
    persist = AsyncMock(return_value=(None, None))
    with (
        patch("app.routers.speech_realtime.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.routers.speech_realtime.live_talk_service.realtime_session_is_active",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.routers.speech_realtime.live_talk_service.load_live_talk_history",
            AsyncMock(return_value=([], False)),
        ),
        patch(
            "app.services.live_talk_tools.search_sources_for_turn", AsyncMock(return_value=sources)
        ),
        patch("app.routers.speech_realtime.live_talk_service.persist_live_talk_turn", persist),
    ):
        response = client.post(
            "/speech/live/persist",
            headers={"Authorization": "Bearer tok"},
            json={
                "chat_id": str(uuid4()),
                "call_id": "issued-session",
                "turn_id": "utterance-1",
                "user_text": "Who won?",
                "assistant_text": "Team A won.",
            },
        )
    assert response.status_code == 204
    assert (
        persist.await_args.kwargs["assistant_text"]
        == "Team A won.\n\n```sources\n" + json.dumps(sources) + "\n```"
    )


def test_realtime_session_returns_ephemeral_key_and_recall_session_id():
    user = _fake_user(plan="pro")
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
        speech_rate_limit_per_minute=0,
    )
    mint = AsyncMock(return_value=RealtimeClientSecretResult(value="ek_test", expires_at=123))
    client = TestClient(_realtime_app(user, settings))
    with _session_mint_patches(mint=mint):
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
    instructions = mint.await_args.kwargs["instructions"]
    assert "UNTRUSTED CONTENT — memory" not in instructions


def test_realtime_session_injects_memory_and_custom_instructions():
    user = _fake_user(plan="pro", custom_instructions="Keep answers short.")
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
        speech_rate_limit_per_minute=0,
    )
    mint = AsyncMock(return_value=RealtimeClientSecretResult(value="ek_test", expires_at=123))
    client = TestClient(_realtime_app(user, settings))
    with _session_mint_patches(mint=mint, memory_block="Lives in Austin"):
        r = client.post(
            "/speech/live/session",
            headers={"Authorization": "Bearer tok"},
            json={},
        )
    assert r.status_code == 200
    instructions = mint.await_args.kwargs["instructions"]
    assert "Lives in Austin" in instructions
    assert "[BEGIN UNTRUSTED CONTENT — memory]" in instructions
    assert "Keep answers short." in instructions
    assert "[BEGIN USER PREFERENCES]" in instructions


def test_realtime_session_mints_when_memory_load_returns_empty():
    user = _fake_user(plan="pro")
    user.memory_enabled = False
    settings = Settings(
        openai_api_key="sk-test",
        speech_live_talk_enabled=True,
        speech_realtime_voice_enabled=True,
        speech_rate_limit_per_minute=0,
    )
    mint = AsyncMock(return_value=RealtimeClientSecretResult(value="ek_test", expires_at=123))
    client = TestClient(_realtime_app(user, settings))
    with _session_mint_patches(mint=mint, memory_block=""):
        r = client.post(
            "/speech/live/session",
            headers={"Authorization": "Bearer tok"},
            json={},
        )
    assert r.status_code == 200
    instructions = mint.await_args.kwargs["instructions"]
    assert "UNTRUSTED CONTENT — memory" not in instructions


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


@pytest.mark.parametrize(
    "case,expected",
    [
        ("valid", 200),
        ("wrong_chat", 403),
        ("missing_chat", 404),
        ("free", 403),
        ("write_tool", 422),
    ],
)
def test_voice_tools_enforce_session_ownership_plan_and_read_only_allowlist(case, expected):
    chat_id = uuid4()
    user = _fake_user(plan="free" if case == "free" else "pro")
    client = TestClient(
        _realtime_app(
            user, Settings(speech_live_talk_enabled=True, speech_realtime_voice_enabled=True)
        )
    )
    redis = AsyncMock()
    redis.get.return_value = str(uuid4() if case == "wrong_chat" else chat_id)
    invoke = AsyncMock(return_value={"content": "verified"})
    with (
        patch("app.routers.speech_realtime.get_redis_client", return_value=redis),
        patch(
            "app.routers.speech_realtime.allow_request_fail_closed", AsyncMock(return_value=True)
        ),
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=None if case == "missing_chat" else MagicMock()),
        ),
        patch("app.services.live_talk_tools.execute_tool", invoke),
    ):
        response = client.post(
            "/speech/live/tool",
            headers={"Authorization": "Bearer tok"},
            json={
                "chat_id": str(chat_id),
                "call_id": "issued-session",
                "turn_id": "utterance-1",
                "name": "send_email" if case == "write_tool" else "web_search",
                "query": "latest score",
            },
        )
    assert response.status_code == expected
    assert invoke.await_count == int(expected == 200)
