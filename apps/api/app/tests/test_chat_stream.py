"""Tests for HTTP SSE chat stream fallback."""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
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
            "app.routers.chat_stream._stream_tokens_sse",
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


@pytest.mark.asyncio
async def test_stream_tokens_sse_stops_on_client_disconnect(monkeypatch):
    """Closing the SSE connection must stop token production, not just this
    relay — otherwise a closed tab leaves the LLM call running to completion,
    still burning provider cost, with tokens streamed to nobody."""
    import app.routers.chat_stream as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)

    cancel_event = asyncio.Event()
    request = AsyncMock()
    poll_count = {"n": 0}

    async def is_disconnected() -> bool:
        poll_count["n"] += 1
        return poll_count["n"] > 2

    request.is_disconnected = is_disconnected

    produced: list[str] = []

    async def stream_factory(result, on_status, on_reasoning):
        for i in range(1000):
            produced.append(str(i))
            yield str(i)
            await asyncio.sleep(0.02)

    chunks = [
        chunk
        async for chunk in chat_stream._stream_tokens_sse(
            chat_id=uuid4(),
            settings=Settings(),
            stream_factory=stream_factory,
            request=request,
            cancel_event=cancel_event,
        )
    ]

    assert cancel_event.is_set()
    assert len(produced) < 1000
    assert any('"type":"start"' in c for c in chunks)


@pytest.mark.asyncio
async def test_stream_tokens_sse_cancels_hung_producer_on_disconnect(monkeypatch):
    """Disconnect must cancel the producer while it is blocked waiting on the
    first LiteLLM chunk — not only between yielded tokens."""
    import app.routers.chat_stream as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)

    cancel_event = asyncio.Event()
    request = AsyncMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def stream_factory(result, on_status, on_reasoning):
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        if False:  # pragma: no cover — keep this an async generator
            yield "x"

    async def _consume() -> list[str]:
        return [
            chunk
            async for chunk in chat_stream._stream_tokens_sse(
                chat_id=uuid4(),
                settings=Settings(),
                stream_factory=stream_factory,
                request=request,
                cancel_event=cancel_event,
            )
        ]

    chunks = await asyncio.wait_for(_consume(), timeout=2.0)
    assert cancel_event.is_set()
    assert started.is_set()
    assert cancelled.is_set()
    assert any('"type":"start"' in c for c in chunks)


@pytest.mark.asyncio
async def test_stream_message_sse_passes_cancel_event_as_should_cancel():
    """The same cancel_event driving disconnect detection must reach the
    actual chat_service call, or a disconnect stops relaying tokens without
    ever stopping the underlying (costly) generation."""
    from app.models.schemas import ChatMessageRequest
    from app.routers.chat_stream import stream_message_sse

    user = _fake_user()
    settings = Settings()
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=True)

    captured_kwargs: dict = {}

    async def fake_stream(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return
        yield  # pragma: no cover - makes this an async generator

    with patch("app.routers.chat_stream.chat_service.stream_chat_response", fake_stream):
        response = await stream_message_sse(
            chat_id=uuid4(),
            body=ChatMessageRequest(content="hi"),
            request=request,
            user=user,
            settings=settings,
        )
        async for _ in response.body_iterator:
            pass

    assert "should_cancel" in captured_kwargs
    assert callable(captured_kwargs["should_cancel"])
