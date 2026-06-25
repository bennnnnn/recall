"""WebSocket endpoint tests."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.gateways.google_auth import create_access_token
from app.main import create_app


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
    uid_str, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_stream(*args, **kwargs):
        yield "Hello"
        yield " world"

    app = _app(user)

    with (
        patch("app.routers.ws.decode_access_token", return_value=user.id),
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
            done = ws.receive_json()
            assert done["type"] == "done"


def test_ws_empty_message_ignored():
    uid_str, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    app = _app(user)

    with (
        patch("app.routers.ws.decode_access_token", return_value=user.id),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "   "})
            # no response expected — unknown type messages are silently skipped
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
        patch("app.routers.ws.decode_access_token", return_value=user.id),
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
            done = ws.receive_json()
            assert done["type"] == "done"


# ── cancel ─────────────────────────────────────────────────────────────────────

def test_ws_cancel_sets_flag():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    cancelled = []

    async def fake_stream(*args, should_cancel=None, **kwargs):
        for word in ["A", "B", "C"]:
            if should_cancel and should_cancel():
                cancelled.append(True)
                return
            yield word

    app = _app(user)

    with (
        patch("app.routers.ws.decode_access_token", return_value=user.id),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=user)),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            # send cancel before message — tests that cancel clears the event
            ws.send_json({"type": "cancel"})
            ws.send_json({"type": "message", "content": "hi"})
            start = ws.receive_json()
            assert start["type"] == "start"


# ── user not found ─────────────────────────────────────────────────────────────

def test_ws_user_not_found_sends_error():
    _, tok = _token()
    chat_id = uuid4()
    app = _app(None)

    with (
        patch("app.routers.ws.decode_access_token", return_value=uuid4()),
        patch("app.routers.ws.auth_service.get_current_user", AsyncMock(return_value=None)),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hello"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "User not found" in err["message"]
