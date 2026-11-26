"""Tests for HTTP SSE chat stream fallback."""

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
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


def _stop_said(shown_chars: int | None = None, *, said: bool = True) -> Any:
    """A stream's ``SseStop`` that finds the user's Stop (or, ``said=False``, none)."""
    from app.modules.chat.sse_stop import StopAsked

    return SimpleNamespace(
        wait=AsyncMock(return_value=StopAsked(shown_chars) if said else None),
        clear_soon=MagicMock(),
    )


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
    no_stop = _stop_said(said=False)
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
        stop=no_stop,
    ):
        pass
    await asyncio.wait_for(finished.wait(), timeout=2.0)

    assert len(produced) == 30
    assert not cancel_event.is_set()
    no_stop.wait.assert_awaited_once()
    no_stop.clear_soon.assert_called_once()  # the stream's key goes with its reply


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
            stop=_stop_said(7),
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
                stop=_stop_said(),
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
            stop=_stop_said(),
        ):
            pass

    await asyncio.wait_for(consume(), timeout=2.0)

    assert result["saved"] == "hello"


@pytest.mark.asyncio
async def test_a_stop_names_its_stream_and_is_read_once(fake_redis):
    """A Stop is the user's, for one chat and one stream: one said late (the reply was
    already saving) can never stop another turn in that chat (review of #2596)."""
    from app.modules.chat.sse_stop import SseStop, StopAsked

    user_id, chat_id, stream_id = uuid4(), uuid4(), uuid4()
    await SseStop(fake_redis, user_id, chat_id, stream_id).ask(12)

    assert await SseStop(fake_redis, uuid4(), chat_id, stream_id).wait(grace=0) is None
    assert await SseStop(fake_redis, user_id, chat_id, uuid4()).wait(grace=0) is None
    stop = SseStop(fake_redis, user_id, chat_id, stream_id)
    assert await stop.wait(grace=0) == StopAsked(12)
    assert await stop.wait(grace=0) is None  # read once


@pytest.mark.asyncio
async def test_a_stop_that_lands_after_the_client_left_still_stops(fake_redis, monkeypatch):
    """The phone says Stop on another connection, which may land after its stream closed:
    the stream waits for it (``STOP_GRACE_SECONDS``)."""
    from app.modules.chat import sse_stop

    monkeypatch.setattr(sse_stop, "_POLL_SECONDS", 0.05)
    stop = sse_stop.SseStop(fake_redis, uuid4(), uuid4(), uuid4())

    async def say_it_late() -> None:
        await asyncio.sleep(1.0)
        await stop.ask(5)

    late = asyncio.create_task(say_it_late())
    assert await stop.wait() == sse_stop.StopAsked(5)
    await late


@pytest.mark.asyncio
async def test_a_streams_stop_key_goes_when_its_reply_is_done(fake_redis):
    from app.core.background_tasks import drain_background_tasks
    from app.modules.chat.sse_stop import SseStop

    stop = SseStop(fake_redis, uuid4(), uuid4(), uuid4())
    await stop.ask(None)
    stop.clear_soon()
    await drain_background_tasks(timeout_seconds=2)

    assert not await fake_redis.exists(stop.key)


def test_the_stop_route_says_stop_for_the_signed_in_users_stream(monkeypatch):
    import app.modules.chat.stream_api as chat_stream
    from app.modules.chat.sse_stop import SseStop

    user = api_user()
    app = app_with_user(user)
    chat_id, stream_id = uuid4(), uuid4()
    said: list[tuple[SseStop, int | None]] = []

    async def ask(self: SseStop, shown_chars: int | None) -> None:
        said.append((self, shown_chars))

    monkeypatch.setattr(SseStop, "ask", ask)
    monkeypatch.setattr(chat_stream, "get_redis_client", lambda: None)
    with patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)):
        client = TestClient(app)
        response = client.post(
            f"/chats/{chat_id}/stream/stop",
            headers={"Authorization": "Bearer tok"},
            json={"stream_id": str(stream_id), "shown_chars": 42},
        )
        refused = [
            client.post(
                f"/chats/{chat_id}/stream/stop",
                headers={"Authorization": "Bearer tok"},
                json=body,
            ).status_code
            for body in ({"stream_id": str(stream_id), "shown_chars": -1}, {"shown_chars": 1})
        ]

    assert response.status_code == 204
    [(stop, shown)] = said
    assert (stop.user_id, stop.chat_id, stop.stream_id, shown) == (user.id, chat_id, stream_id, 42)
    assert refused == [422, 422]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["message", "regenerate"])
async def test_both_sse_routes_read_the_stop_of_the_stream_they_were_named(monkeypatch, route):
    import app.modules.chat.stream_api as chat_stream
    from app.models.schemas import ChatMessageRequest

    seen: dict[str, Any] = {}

    def capture(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return _fake_sse_stream()

    monkeypatch.setattr(chat_stream, "_stream_tokens_sse", capture)
    stream_id, chat_id = uuid4(), uuid4()
    endpoint = (
        chat_stream.stream_message_sse if route == "message" else chat_stream.stream_regenerate_sse
    )
    redis = MagicMock()
    await endpoint(
        chat_id=chat_id,
        body=ChatMessageRequest(content="hi", stream_id=stream_id),
        request=AsyncMock(),
        user=(user := api_user()),
        settings=Settings(),
        redis=redis,
    )

    stop = seen["stop"]
    assert (stop.redis, stop.user_id, stop.chat_id, stop.stream_id) == (
        redis,
        user.id,
        chat_id,
        stream_id,
    )


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
