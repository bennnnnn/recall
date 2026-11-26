"""Tests for HTTP SSE chat stream fallback."""

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.tests.api_support import api_user, app_with_user


async def _fake_sse_stream(*_args, **_kwargs):
    yield 'data: {"type":"start"}\n\n'
    yield 'data: {"type":"token","content":"Hi"}\n\n'
    yield 'data: {"type":"stream_end"}\n\n'
    yield 'data: {"type":"done","message_id":"msg-1"}\n\n'


@pytest.mark.asyncio
async def test_sse_attachment_rejection_is_explicit_and_never_done():
    import json

    from app.exceptions import AttachmentValidationError
    from app.modules.chat.stream_api import _stream_tokens_sse

    async def rejected(*args, **kwargs):
        raise AttachmentValidationError("Attach the file again.")
        yield  # pragma: no cover

    request = AsyncMock()
    request.is_disconnected.return_value = False
    chunks = [
        chunk
        async for chunk in _stream_tokens_sse(
            chat_id=uuid4(), stream_factory=rejected, request=request
        )
    ]
    events = [json.loads(chunk.removeprefix("data: ")) for chunk in chunks]
    assert [event["type"] for event in events] == ["start", "error"]
    assert events[-1]["code"] == "attachment_rejected"


def test_stream_message_sse_returns_event_stream():
    user = api_user()
    app = app_with_user(user)
    chat_id = uuid4()

    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
        patch(
            "app.modules.chat.stream_api.allow_chat_message",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.chat.stream_api._stream_tokens_sse",
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
    from app.modules.chat.stream_api import _sse

    assert _sse({"type": "start"}) == 'data: {"type":"start"}\n\n'


def _stop_said(shown_chars: int | None = None):
    """A ``stop_check`` that finds the user's Stop (``sse_stop.wait_for_stop``)."""
    from app.modules.chat.sse_stop import StopAsked

    return AsyncMock(return_value=StopAsked(shown_chars))


@pytest.mark.asyncio
async def test_a_dropped_sse_stream_finishes_and_saves_its_reply(monkeypatch):
    """A connection that drops with no Stop said (a tunnel, the app in the background) is
    no Stop: the reply runs on and saves whole, as the socket's does. It used to save cut
    short as the user's Stop, with no checked cards and no Continue (security review,
    2026-11-25)."""
    import app.modules.chat.stream_api as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)
    cancel_event = asyncio.Event()
    request = AsyncMock()
    request.is_disconnected = AsyncMock(side_effect=[False, False, *([True] * 100)])
    no_stop = AsyncMock(return_value=None)
    produced: list[str] = []
    finished = asyncio.Event()

    async def stream_factory(_result, _on_status, _on_reasoning, should_cancel):
        for i in range(30):
            if should_cancel():
                return
            produced.append(str(i))
            yield str(i)
            await asyncio.sleep(0.005)
        finished.set()

    async for _chunk in chat_stream._stream_tokens_sse(
        chat_id=uuid4(),
        stream_factory=stream_factory,
        request=request,
        cancel_event=cancel_event,
        stop_check=no_stop,
    ):
        pass
    await asyncio.wait_for(finished.wait(), timeout=2.0)

    assert len(produced) == 30
    assert not cancel_event.is_set()
    no_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_users_stop_said_over_sse_stops_the_reply(monkeypatch):
    """The Stop the phone says on its own request stops the reply once its stream closes,
    with how much the phone drew."""
    import app.modules.chat.stream_api as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)
    cancel_event = asyncio.Event()
    request = AsyncMock()
    poll_count = {"n": 0}

    async def is_disconnected() -> bool:
        poll_count["n"] += 1
        return poll_count["n"] > 2

    request.is_disconnected = is_disconnected
    produced: list[str] = []
    outcomes: list[object] = []

    async def stream_factory(outcome, _on_status, _on_reasoning, _should_cancel):
        outcomes.append(outcome)
        for i in range(1000):
            produced.append(str(i))
            yield str(i)
            await asyncio.sleep(0.02)

    chunks = [
        chunk
        async for chunk in chat_stream._stream_tokens_sse(
            chat_id=uuid4(),
            stream_factory=stream_factory,
            request=request,
            cancel_event=cancel_event,
            stop_check=_stop_said(7),
        )
    ]

    assert cancel_event.is_set()
    assert len(produced) < 1000
    assert any('"type":"start"' in c for c in chunks)
    assert outcomes[0].client_shown_chars == 7


@pytest.mark.asyncio
async def test_stream_tokens_sse_registers_inflight_producer(monkeypatch):
    """GET /messages waits on the SSE producer the same way it waits on WS."""
    import app.modules.chat.stream_api as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=False)
    chat_id = uuid4()
    registered: list[object] = []
    original = chat_stream.register_inflight_stream

    def capture(cid: object, task: object, *, stop: object) -> None:
        registered.append(cid)
        assert callable(stop)
        original(cid, task, stop=stop)

    monkeypatch.setattr(chat_stream, "register_inflight_stream", capture)

    async def stream_factory(_result, _on_status, _on_reasoning, _should_cancel):
        yield "hi"

    chunks = [
        chunk
        async for chunk in chat_stream._stream_tokens_sse(
            chat_id=chat_id,
            stream_factory=stream_factory,
            request=request,
            cancel_event=asyncio.Event(),
        )
    ]
    assert registered == [chat_id]
    assert any('"type":"token"' in c for c in chunks)


@pytest.mark.asyncio
async def test_the_users_stop_cancels_a_producer_waiting_on_the_model(monkeypatch):
    """A Stop must cancel the producer while it is blocked waiting on the first LiteLLM
    chunk, not only between yielded tokens."""
    import app.modules.chat.stream_api as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)

    cancel_event = asyncio.Event()
    request = AsyncMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def stream_factory(_result, _on_status, _on_reasoning, _should_cancel):
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
                stream_factory=stream_factory,
                request=request,
                cancel_event=cancel_event,
                stop_check=_stop_said(),
            )
        ]

    chunks = await asyncio.wait_for(_consume(), timeout=2.0)
    assert cancel_event.is_set()
    assert started.is_set()
    assert cancelled.is_set()
    assert any('"type":"start"' in c for c in chunks)


@pytest.mark.asyncio
async def test_a_cancelled_sse_response_leaves_the_reply_running_to_its_save(monkeypatch):
    """Dropping the socket cancels this generator; the reply is not stopped by it and still
    finishes (the producer saves it)."""
    import app.modules.chat.stream_api as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=False)
    finished = asyncio.Event()

    async def stream_factory(_result, _on_status, _on_reasoning, _should_cancel):
        yield "hello "
        await asyncio.sleep(0.05)
        yield "world"
        finished.set()

    seen = asyncio.Event()

    async def consume() -> None:
        async for chunk in chat_stream._stream_tokens_sse(
            chat_id=uuid4(),
            stream_factory=stream_factory,
            request=request,
            cancel_event=asyncio.Event(),
        ):
            if "hello" in chunk:
                seen.set()

    task = asyncio.create_task(consume())
    await asyncio.wait_for(seen.wait(), timeout=2.0)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    await asyncio.wait_for(finished.wait(), timeout=2.0)


@pytest.mark.asyncio
async def test_a_stop_resumes_the_generator_parked_at_yield(monkeypatch):
    """A Stop between tokens parks the generator at yield. Resume it so the reply is saved."""
    import app.modules.chat.stream_api as chat_stream

    monkeypatch.setattr(chat_stream, "_DISCONNECT_POLL_SECONDS", 0.01)
    parked = asyncio.Event()

    async def is_disconnected() -> bool:
        return parked.is_set()

    request = AsyncMock()
    request.is_disconnected = is_disconnected
    result: dict[str, object] = {}

    class _HoldTokenQueue(asyncio.Queue):
        async def put(self, item: object) -> None:
            if isinstance(item, tuple) and item and item[0] == "token":
                parked.set()
                await asyncio.Event().wait()
            await super().put(item)

    async def stream_factory(_result, _on_status, _on_reasoning, should_cancel):
        yield "hello "
        if should_cancel():
            result["saved"] = "hello"
            return
        await asyncio.sleep(30)

    async def consume() -> None:
        async for _chunk in chat_stream._stream_tokens_sse(
            chat_id=uuid4(),
            stream_factory=stream_factory,
            request=request,
            cancel_event=asyncio.Event(),
            queue_factory=_HoldTokenQueue,
            stop_check=_stop_said(),
        ):
            pass

    await asyncio.wait_for(consume(), timeout=2.0)

    assert result["saved"] == "hello"


@pytest.mark.asyncio
async def test_a_stop_is_said_for_the_users_own_chat_and_read_once(fake_redis):
    from app.modules.chat.sse_stop import StopAsked, ask_stop, wait_for_stop

    user_id, chat_id = uuid4(), uuid4()
    await ask_stop(fake_redis, user_id, chat_id, 12)

    assert await wait_for_stop(fake_redis, uuid4(), chat_id, grace=0) is None  # another user
    assert await wait_for_stop(fake_redis, user_id, chat_id, grace=0) == StopAsked(12)
    assert await wait_for_stop(fake_redis, user_id, chat_id, grace=0) is None  # read once


def test_the_stop_route_says_stop_for_the_signed_in_user(monkeypatch):
    import app.modules.chat.stream_api as chat_stream

    user = api_user()
    app = app_with_user(user)
    chat_id = uuid4()
    ask = AsyncMock()
    monkeypatch.setattr(chat_stream, "ask_stop", ask)
    monkeypatch.setattr(chat_stream, "get_redis_client", lambda: None)
    with patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)):
        client = TestClient(app)
        response = client.post(
            f"/chats/{chat_id}/stream/stop",
            headers={"Authorization": "Bearer tok"},
            json={"shown_chars": 42},
        )
        refused = client.post(
            f"/chats/{chat_id}/stream/stop",
            headers={"Authorization": "Bearer tok"},
            json={"shown_chars": -1},
        )

    assert response.status_code == 204
    _redis, user_id, stopped_chat, shown = ask.await_args.args
    assert (user_id, stopped_chat, shown) == (user.id, chat_id, 42)
    assert refused.status_code == 422


@pytest.mark.asyncio
async def test_stream_message_sse_passes_cancel_event_as_should_cancel():
    """The same cancel_event driving disconnect detection must reach the
    actual stream_entry call, or a disconnect stops relaying tokens without
    ever stopping the underlying (costly) generation."""
    from app.models.schemas import ChatMessageRequest
    from app.modules.chat.stream_api import stream_message_sse

    user = api_user()
    settings = Settings()
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=True)

    captured_kwargs: dict = {}

    async def fake_stream(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return
        yield  # pragma: no cover - makes this an async generator

    with (
        patch(
            "app.modules.chat.stream_api.allow_chat_message",
            AsyncMock(return_value=True),
        ),
        patch("app.modules.chat.stream_api.stream_entry.stream_chat_response", fake_stream),
    ):
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


@pytest.mark.parametrize(
    "path, body",
    [
        ("messages/stream", {"content": "hello"}),
        ("regenerate/stream", {}),
    ],
)
def test_stream_routes_return_429_when_chat_rate_limited(path: str, body: dict):
    """Streaming routes share require_chat_rate_limit; each must 429.

    The check used to be copy-pasted into every route body, so a new streaming
    entry point could silently ship without it. This pins the throttle to the
    routes themselves rather than to any one handler.
    """
    user = api_user()
    app = app_with_user(user)
    chat_id = uuid4()

    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
        patch(
            "app.modules.chat.stream_api.allow_chat_message",
            AsyncMock(return_value=False),
        ),
    ):
        client = TestClient(app)
        response = client.post(
            f"/chats/{chat_id}/{path}",
            headers={"Authorization": "Bearer tok"},
            json=body,
        )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    # Coded: with the English alone, a Regenerate over the limit said "Couldn't reach the
    # server" on the phone.
    assert response.json() == {
        "detail": {"code": "rate_limited", "message": "Too many chat requests. Try again shortly."}
    }
