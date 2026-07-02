"""WebSocket endpoint tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.exceptions import QuotaExceededError
from app.gateways.google_auth import create_access_token
from app.main import create_app
from app.services.quota import QUOTA_EXCEEDED_MESSAGE


@pytest.fixture(autouse=True)
def _ws_rate_limit():
    with patch("app.routers.ws.allow_request", AsyncMock(return_value=True)):
        yield


def _settings():
    return Settings(
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!",
        dev_auth_enabled=True,
    )


def _token(uid=None):
    uid = uid or uuid4()
    return str(uid), create_access_token(uid, _settings())


def _fake_user(uid=None):
    user = MagicMock()
    user.id = uid or uuid4()
    user.default_model = "free-chat"
    user.response_style = "balanced"
    user.memory_enabled = True
    return user


def _app(user):
    from app.core.deps import get_settings_dep

    app = create_app()
    app.dependency_overrides[get_settings_dep] = _settings
    return app


async def _empty_stream(*args, **kwargs):
    return
    yield  # make it an async generator


# ── auth failure ───────────────────────────────────────────────────────────────


def test_ws_missing_token_closes():
    app = _app(None)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/chats/{uuid4()}") as ws:
        ws.send_json({})
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "Missing token" in msg["message"]


def test_ws_invalid_token_closes():
    app = _app(None)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/chats/{uuid4()}") as ws:
        ws.send_json({"token": "not-a-valid-jwt"})
        msg = ws.receive_json()
    assert msg["type"] == "error"


# ── normal message flow ────────────────────────────────────────────────────────


def test_ws_sends_message_and_receives_tokens():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_stream(*args, **kwargs):
        yield "Hello"
        yield " world"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi"})
            start = ws.receive_json()
            assert start["type"] == "start"
            token1 = ws.receive_json()
            assert token1["type"] == "token"
            assert token1["content"] == "Hello"
            token2 = ws.receive_json()
            assert token2["type"] == "token"
            assert ws.receive_json()["type"] == "stream_end"
            done = ws.receive_json()
            assert done["type"] == "done"


def test_ws_passes_client_timezone_to_stream():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_stream(*args, **kwargs):
        assert kwargs.get("client_timezone") == "America/Los_Angeles"
        yield "ok"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok, "client_timezone": "America/Los_Angeles"})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["type"] == "token"
            assert ws.receive_json()["type"] == "stream_end"
            assert ws.receive_json()["type"] == "done"


def test_ws_empty_message_ignored():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "   "})
            ws.send_json({"type": "unknown"})


# ── regenerate ─────────────────────────────────────────────────────────────────


def test_ws_regenerate():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_regen(*args, **kwargs):
        yield "Regen"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_regenerate_response", fake_regen),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "regenerate"})
            start = ws.receive_json()
            assert start["type"] == "start"
            token = ws.receive_json()
            assert token["content"] == "Regen"
            assert ws.receive_json()["type"] == "stream_end"
            done = ws.receive_json()
            assert done["type"] == "done"


def test_ws_regenerate_passes_client_geo():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_regen(*args, **kwargs):
        assert kwargs.get("client_location") == "San Francisco, CA"
        assert kwargs.get("client_latitude") == 37.77
        assert kwargs.get("client_longitude") == -122.42
        yield "nearby"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_regenerate_response", fake_regen),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json(
                {
                    "type": "regenerate",
                    "client_location": "San Francisco, CA",
                    "client_latitude": 37.77,
                    "client_longitude": -122.42,
                }
            )
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["type"] == "token"
            assert ws.receive_json()["type"] == "stream_end"
            assert ws.receive_json()["type"] == "done"


# ── cancel ─────────────────────────────────────────────────────────────────────


def test_ws_cancel_sets_flag():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_stream(*args, should_cancel=None, **kwargs):
        for word in ["A", "B", "C"]:
            if should_cancel and should_cancel():
                return
            yield word

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "cancel"})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            while True:
                msg = ws.receive_json()
                if msg["type"] == "done":
                    break


def test_ws_mid_stream_cancel():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def slow_stream(*args, should_cancel=None, **kwargs):
        for word in ["one", "two", "three", "four"]:
            if should_cancel and should_cancel():
                return
            yield word
            await asyncio.sleep(0.05)

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_chat_response", slow_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            first = ws.receive_json()
            assert first["type"] == "token"
            ws.send_json({"type": "cancel"})
            assert ws.receive_json()["type"] == "stream_end"
            done = ws.receive_json()
            assert done["type"] == "done"


# ── validation / service errors ────────────────────────────────────────────────


def test_ws_invalid_message_payload():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi", "model": "not-a-model"})
            err = ws.receive_json()
            assert err["type"] == "error"


def test_ws_quota_error_frame():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def quota_fail(*args, **kwargs):
        raise QuotaExceededError(QUOTA_EXCEEDED_MESSAGE)
        yield  # pragma: no cover

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_chat_response", quota_fail),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "quota_exceeded"
            assert "limit" in err["message"].lower()


# ── user not found ─────────────────────────────────────────────────────────────


def test_ws_user_not_found_sends_error():
    _, tok = _token()
    chat_id = uuid4()
    app = _app(None)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=uuid4()),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=None)),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hello"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "User not found" in err["message"]


def test_ws_edit_message():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    message_id = uuid4()

    async def fake_edit(*args, **kwargs):
        yield "Edited"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_edit_response", fake_edit),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json(
                {
                    "type": "edit",
                    "message_id": str(message_id),
                    "content": "updated text",
                }
            )
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["content"] == "Edited"
            assert ws.receive_json()["type"] == "stream_end"
            assert ws.receive_json()["type"] == "done"


def test_ws_edit_passes_client_geo():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    message_id = uuid4()

    async def fake_edit(*args, **kwargs):
        assert kwargs.get("client_location") == "Oakland, CA"
        assert kwargs.get("client_latitude") == 37.8
        assert kwargs.get("client_longitude") == -122.27
        yield "Edited"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_edit_response", fake_edit),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json(
                {
                    "type": "edit",
                    "message_id": str(message_id),
                    "content": "coffee near me",
                    "client_location": "Oakland, CA",
                    "client_latitude": 37.8,
                    "client_longitude": -122.27,
                }
            )
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["content"] == "Edited"
            assert ws.receive_json()["type"] == "stream_end"
            assert ws.receive_json()["type"] == "done"


def test_ws_edit_invalid_payload():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "edit", "content": "missing message id"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "Invalid edit" in err["message"]
