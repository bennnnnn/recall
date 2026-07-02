"""Tests for HTTP SSE chat stream fallback."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.tests.test_routers import _app_with_user, _fake_user


async def _fake_sse_stream(*_args, **_kwargs):
    yield 'data: {"type":"start"}\n\n'
    yield 'data: {"type":"token","content":"Hi"}\n\n'
    yield 'data: {"type":"stream_end"}\n\n'
    yield 'data: {"type":"done","message_id":"msg-1"}\n\n'


def test_stream_message_sse_returns_event_stream():
    user = _fake_user()
    app = _app_with_user(user)
    chat_id = uuid4()

    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
        patch(
            "app.routers.chat_stream._stream_chat_sse",
            side_effect=_fake_sse_stream,
        ),
    ):
        client = TestClient(app)
        response = client.post(
            f"/chats/{chat_id}/messages/stream",
            headers={"Authorization": "Bearer tok"},
            json={"content": "hello"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"start"' in response.text
    assert '"type":"token"' in response.text
    assert '"type":"done"' in response.text


def test_sse_payload_format():
    from app.routers.chat_stream import _sse

    assert _sse({"type": "start"}) == 'data: {"type":"start"}\n\n'
