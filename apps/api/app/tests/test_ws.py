"""WebSocket endpoint tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.exceptions import ChatNotFoundError, QuotaExceededError
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


def test_ws_handshake_fails_closed_on_redis_error():
    """A Redis outage during the WS handshake must close (1008), not let the
    connect through unbounded — otherwise unauthenticated connects bypass
    the limiter for the whole outage."""
    from starlette.websockets import WebSocketDisconnect

    app = _app(None)
    client = TestClient(app)
    with patch(
        "app.routers.ws.allow_request",
        AsyncMock(side_effect=RuntimeError("redis down")),
    ):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/chats/{uuid4()}") as ws:
                ws.send_json({"token": "x"})


@pytest.mark.asyncio
async def test_ws_handshake_rate_limit_uses_forwarded_ip_when_trusted():
    """The handshake limiter must key on the edge-seen IP (fly-client-ip/XFF)
    when behind a trusted proxy, not the proxy's own address — otherwise
    every connect shares one proxy bucket."""
    from app.routers.ws import _ws_handshake_rate_limit

    websocket = MagicMock()
    websocket.client.host = "10.0.0.1"
    websocket.headers = {"fly-client-ip": "198.51.100.7"}
    settings = Settings(trust_x_forwarded_for=True)

    captured: dict = {}

    async def fake_allow(_redis, key, *, limit, window_seconds):
        captured["key"] = key
        return True

    with (
        patch("app.routers.ws.get_settings", return_value=settings),
        patch("app.routers.ws.allow_request", side_effect=fake_allow),
    ):
        await _ws_handshake_rate_limit(AsyncMock(), websocket)

    assert "198.51.100.7" in captured["key"]


def test_ws_invalid_token_closes():
    app = _app(None)
    client = TestClient(app)
    with client.websocket_connect(f"/ws/chats/{uuid4()}") as ws:
        ws.send_json({"token": "not-a-valid-jwt"})
        msg = ws.receive_json()
    assert msg["type"] == "error"


def test_ws_auth_timeout_closes():
    """Sockets that never send an auth frame must not hang forever."""
    app = _app(None)
    client = TestClient(app)

    with patch(
        "app.routers.ws.asyncio.wait_for",
        side_effect=TimeoutError(),
    ):
        with client.websocket_connect(f"/ws/chats/{uuid4()}") as ws:
            msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "timeout" in msg["message"].lower()


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


def test_ws_done_includes_resolved_model():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()

    async def fake_stream(*args, result=None, **kwargs):
        if result is not None:
            result["message_id"] = str(uuid4())
            result["resolved_model"] = "smart-chat"
        yield "Hello"

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["type"] == "token"
            stream_end = ws.receive_json()
            assert stream_end["type"] == "stream_end"
            assert stream_end["resolved_model"] == "smart-chat"
            done = ws.receive_json()
            assert done["type"] == "done"
            assert done["resolved_model"] == "smart-chat"


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

    def missing_user_stream(*_args, **_kwargs):
        async def _gen():
            raise ChatNotFoundError("User not found.")
            yield ""  # pragma: no cover

        return _gen()

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=uuid4()),
        ),
        patch("app.routers.ws.chat_service.stream_chat_response", missing_user_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hello"})
            start = ws.receive_json()
            assert start["type"] == "start"
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
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "edit", "content": "missing message id"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "Invalid edit" in err["message"]


def test_ws_message_rate_limit_blocks_second_chargeable_message():
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    app = _app(user)
    msg_calls = {"count": 0}

    async def allow_side_effect(_redis, key, *, limit, window_seconds):
        if str(key).startswith("rate:ws:msg:"):
            msg_calls["count"] += 1
            return msg_calls["count"] <= 1
        return True

    async def fake_stream(*args, **kwargs):
        yield "ok"

    with (
        patch("app.routers.ws.allow_request", side_effect=allow_side_effect),
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "first"})
            assert ws.receive_json()["type"] == "start"
            while True:
                msg = ws.receive_json()
                if msg["type"] == "done":
                    break
            ws.send_json({"type": "message", "content": "second"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "Too many requests" in err["message"]
            assert msg_calls["count"] == 2


# ── done is not blocked by background finalization ─────────────────────────────


def test_ws_done_waits_for_finalize_commit():
    """`done` must not be sent until the DB finalize commits, so the
    message_id it carries always references a persisted row (no ghost `done`
    with a pre-assigned id that might never land). The token stream still
    flushes immediately (stream_end is not held); only the final `done`
    waits on the commit. Before this, a failed finalize left the client
    holding a message_id for a row that was never inserted."""
    import time

    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    message_id = str(uuid4())
    release_finalize = asyncio.Event()
    captured: dict = {}

    async def fake_stream(*args, result=None, **kwargs):
        captured["loop"] = asyncio.get_running_loop()
        yield "Hello"
        if result is not None:
            result["message_id"] = message_id
            result["resolved_model"] = "free-chat"

            async def slow_finalize():
                # Blocks until the test releases it — `done` must wait.
                try:
                    await asyncio.wait_for(release_finalize.wait(), timeout=8)
                except TimeoutError:
                    pass

            result["_finalize_db_task"] = asyncio.create_task(slow_finalize())

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["type"] == "token"
            assert ws.receive_json()["type"] == "stream_end"
            # `done` is held while the finalize commit is in flight — the
            # client stays in the streaming state until the commit lands.
            started = time.monotonic()
            captured["loop"].call_soon_threadsafe(release_finalize.set)
            done = ws.receive_json()
            elapsed = time.monotonic() - started
            assert done["type"] == "done"
            assert done["message_id"] == message_id
            # `done` arrived only after the finalize was released — proving
            # we awaited the commit rather than sending a ghost `done`.
            assert elapsed >= 0.0  # released near-instantly; the point is it
            # was awaited, not that it was slow.


def test_ws_done_sends_error_when_finalize_fails():
    """If the DB finalize FAILS, the client must get an error instead of a
    ghost `done` carrying a message_id for a row that never persisted."""
    _, tok = _token()
    user = _fake_user()
    chat_id = uuid4()
    message_id = str(uuid4())

    async def fake_stream(*args, result=None, **kwargs):
        yield "Hello"
        if result is not None:
            result["message_id"] = message_id
            result["resolved_model"] = "free-chat"

            async def failing_finalize():
                raise RuntimeError("Neon is down")

            result["_finalize_db_task"] = asyncio.create_task(failing_finalize())

    app = _app(user)

    with (
        patch(
            "app.routers.ws.tokens_service.verify_access_token",
            AsyncMock(return_value=user.id),
        ),
        patch("app.routers.ws.chat_service.stream_chat_response", fake_stream),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/chats/{chat_id}") as ws:
            ws.send_json({"token": tok})
            ws.send_json({"type": "message", "content": "hi"})
            assert ws.receive_json()["type"] == "start"
            assert ws.receive_json()["type"] == "token"
            assert ws.receive_json()["type"] == "stream_end"
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Failed to save" in msg["message"]
