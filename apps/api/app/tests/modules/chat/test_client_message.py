"""One turn per client message: a resend of a message the server took never runs twice.

The phone sends a message again, with the same ``client_message_id``, when its
socket went quiet before ``start`` (the first send may or may not have arrived),
over SSE, or from Retry. Without the claim a resend after the first turn finished
was a second turn: the same question answered and charged twice.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import ExitStack
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.access_tokens import create_access_token
from app.core.config import Settings
from app.exceptions import QuotaExceededError
from app.main import create_app
from app.modules.chat import client_message
from app.modules.chat.client_message import (
    CLAIM_RUNNING_TTL_SECONDS,
    CLAIM_SAVED_TTL_SECONDS,
    UNNAMED,
    claim_client_message,
    claim_key,
)
from app.modules.chat.turn_outcome import TurnOutcome

_SECRET = "super-secret-key-that-is-at-least-32-chars!!"


# ── the claim ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_client_message_without_a_name_is_never_a_duplicate(fake_redis) -> None:
    for _ in range(2):
        claim = await claim_client_message(
            fake_redis, user_id=uuid4(), chat_id=uuid4(), client_message_id=None
        )
        assert claim is UNNAMED
    assert await fake_redis.dbsize() == 0


@pytest.mark.asyncio
async def test_claim_client_message_lets_one_turn_take_a_name(fake_redis) -> None:
    user_id, chat_id, name = uuid4(), uuid4(), uuid4()
    first = await claim_client_message(
        fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
    )
    again = await claim_client_message(
        fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
    )
    other_chat = await claim_client_message(
        fake_redis, user_id=user_id, chat_id=uuid4(), client_message_id=name
    )
    assert first is not None and first is not UNNAMED
    assert again is None
    assert other_chat is not None
    ttl = await fake_redis.ttl(claim_key(user_id, chat_id, name))
    assert 0 < ttl <= CLAIM_RUNNING_TTL_SECONDS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome, kept",
    [
        (TurnOutcome(), False),
        (TurnOutcome(user_message_saved=True), True),
        (TurnOutcome(message_id="reply"), True),
    ],
    ids=["nothing-saved", "message-saved", "reply-saved"],
)
async def test_claim_settle_frees_an_unsaved_turn_and_keeps_a_saved_one(
    fake_redis, outcome: TurnOutcome, kept: bool
) -> None:
    user_id, chat_id, name = uuid4(), uuid4(), uuid4()
    claim = await claim_client_message(
        fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
    )
    assert claim is not None
    await claim.settle(outcome)
    ttl = await fake_redis.ttl(claim_key(user_id, chat_id, name))
    if kept:
        assert CLAIM_RUNNING_TTL_SECONDS < ttl <= CLAIM_SAVED_TTL_SECONDS
    else:
        assert ttl == -2  # gone: a resend after a refusal runs
        resend = await claim_client_message(
            fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
        )
        assert resend is not None


@pytest.mark.asyncio
async def test_claim_client_message_fails_open_when_redis_errors() -> None:
    redis = MagicMock()
    redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
    claim = await claim_client_message(
        redis, user_id=uuid4(), chat_id=uuid4(), client_message_id=uuid4()
    )
    assert claim is UNNAMED


@pytest.mark.asyncio
async def test_claim_settle_never_raises() -> None:
    redis = MagicMock()
    redis.delete = AsyncMock(side_effect=ConnectionError("redis down"))
    await client_message.ClientMessageClaim(redis, "key").settle(TurnOutcome())
    redis.delete.assert_awaited_once_with("key")


# ── over the socket ────────────────────────────────────────────────────────────


def _socket_client(user_id: UUID, redis: Any) -> tuple[TestClient, ExitStack]:
    from app.core.deps import get_settings_dep

    settings = Settings(jwt_secret=_SECRET, dev_auth_enabled=True)
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: settings
    stack = ExitStack()
    stack.enter_context(patch("app.modules.chat.ws_api.get_settings", return_value=settings))
    stack.enter_context(patch("app.modules.chat.ws_api.get_redis_client", return_value=redis))
    stack.enter_context(
        patch("app.modules.chat.ws_api.allow_request_fail_closed", AsyncMock(return_value=True))
    )
    stack.enter_context(
        patch("app.core.chat_rate_limit.allow_chat_message", AsyncMock(return_value=True))
    )
    stack.enter_context(
        patch(
            "app.modules.chat.ws_api.access_tokens.verify_access_token",
            AsyncMock(return_value=user_id),
        )
    )
    stack.enter_context(
        patch(
            "app.modules.chat.ws_api.stream_entry.stream_chat_response",
            _counted_turn,
        )
    )
    return TestClient(app), stack


_turns: list[str] = []


async def _counted_turn(*_args: Any, outcome: TurnOutcome, content: str, **_kwargs: Any):
    _turns.append(content)
    if content == "over quota":
        raise QuotaExceededError("Daily limit reached.")
    outcome.mark_user_message_saved()
    yield "answer"


@pytest.fixture(autouse=True)
def _no_turns_yet():
    _turns.clear()


def _auth(socket: Any, user_id: UUID) -> None:
    settings = Settings(jwt_secret=_SECRET, dev_auth_enabled=True)
    socket.send_json({"token": create_access_token(user_id, settings)})


_TURN = ["start", "token", "stream_end", "done"]


def test_ws_answers_ping_between_turns_and_during_one() -> None:
    user_id, chat_id = uuid4(), uuid4()
    client, stack = _socket_client(user_id, fakeredis.aioredis.FakeRedis(decode_responses=True))
    with stack, client.websocket_connect(f"/ws/chats/{chat_id}") as socket:
        _auth(socket, user_id)
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        socket.send_json({"type": "message", "content": "hi"})
        assert [socket.receive_json()["type"] for _ in range(4)] == _TURN


def test_ws_resent_message_is_followed_not_run_twice() -> None:
    """Regression: the phone resends a message whose socket went quiet before
    ``start``; the first send had arrived and its turn already answered."""
    user_id, chat_id, name = uuid4(), uuid4(), str(uuid4())
    client, stack = _socket_client(user_id, fakeredis.aioredis.FakeRedis(decode_responses=True))
    frame = {"type": "message", "content": "hi", "client_message_id": name}
    with stack:
        with client.websocket_connect(f"/ws/chats/{chat_id}") as first:
            _auth(first, user_id)
            first.send_json(frame)
            assert [first.receive_json()["type"] for _ in range(4)] == _TURN
        with client.websocket_connect(f"/ws/chats/{chat_id}") as resend:
            _auth(resend, user_id)
            resend.send_json(frame)
            assert resend.receive_json() == {"type": "duplicate"}
            # The socket stays usable: the next message is a new turn.
            resend.send_json({"type": "message", "content": "next", "client_message_id": None})
            assert [resend.receive_json()["type"] for _ in range(4)] == _TURN
    assert _turns == ["hi", "next"]


def test_ws_refused_message_frees_its_name_for_the_resend() -> None:
    user_id, chat_id, name = uuid4(), uuid4(), str(uuid4())
    client, stack = _socket_client(user_id, fakeredis.aioredis.FakeRedis(decode_responses=True))
    frame = {"type": "message", "content": "over quota", "client_message_id": name}
    with stack, client.websocket_connect(f"/ws/chats/{chat_id}") as socket:
        _auth(socket, user_id)
        for _ in range(2):
            socket.send_json(frame)
            assert socket.receive_json()["type"] == "start"
            error = socket.receive_json()
            assert error["type"] == "error"
            assert error["user_message_saved"] is False
    assert _turns == ["over quota", "over quota"]


@pytest.mark.asyncio
async def test_ws_turn_frees_its_claim_when_start_cannot_be_sent(fake_redis) -> None:
    """A phone that closed the socket before ``start`` got no turn: its resend runs."""
    from app.modules.chat.ws_turn import run_chat_stream

    user_id, chat_id, name = uuid4(), uuid4(), uuid4()
    claim = await claim_client_message(
        fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
    )
    assert claim is not None
    gone = MagicMock()
    gone.send_json = AsyncMock(side_effect=RuntimeError("WebSocket is not connected"))
    factory = MagicMock()
    await run_chat_stream(gone, cancel_event=MagicMock(), stream_factory=factory, claim=claim)
    factory.assert_not_called()
    assert await fake_redis.exists(claim_key(user_id, chat_id, name)) == 0


# ── over SSE ───────────────────────────────────────────────────────────────────


def _request() -> Any:
    request = AsyncMock()
    request.is_disconnected = AsyncMock(return_value=False)
    return request


async def _events(body: AsyncIterator[str]) -> list[dict[str, Any]]:
    return [json.loads(chunk.removeprefix("data: ")) async for chunk in body]


@pytest.mark.asyncio
async def test_sse_resend_of_a_taken_message_is_followed_not_run_twice(fake_redis) -> None:
    from app.modules.chat.stream_api import _stream_tokens_sse

    user_id, chat_id, name = uuid4(), uuid4(), uuid4()
    runs: list[str] = []

    def factory(outcome: TurnOutcome, *_args: Any) -> AsyncIterator[str]:
        async def turn() -> AsyncIterator[str]:
            runs.append("turn")
            outcome.mark_user_message_saved()
            yield "answer"

        return turn()

    def claim() -> Any:
        return claim_client_message(
            fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
        )

    first = await _events(
        _stream_tokens_sse(
            chat_id=chat_id, stream_factory=factory, request=_request(), claim_message=claim
        )
    )
    resend = await _events(
        _stream_tokens_sse(
            chat_id=chat_id, stream_factory=factory, request=_request(), claim_message=claim
        )
    )
    assert [event["type"] for event in first] == ["start", "token", "stream_end", "done"]
    assert resend == [{"type": "duplicate"}]
    assert runs == ["turn"]
    ttl = await fake_redis.ttl(claim_key(user_id, chat_id, name))
    assert ttl > CLAIM_RUNNING_TTL_SECONDS


@pytest.mark.asyncio
async def test_sse_refused_message_frees_its_name(fake_redis) -> None:
    from app.modules.chat.stream_api import _stream_tokens_sse

    user_id, chat_id, name = uuid4(), uuid4(), uuid4()

    def refused(*_args: Any) -> AsyncIterator[str]:
        async def turn() -> AsyncIterator[str]:
            raise QuotaExceededError("Daily limit reached.")
            yield  # pragma: no cover

        return turn()

    events = await _events(
        _stream_tokens_sse(
            chat_id=chat_id,
            stream_factory=refused,
            request=_request(),
            claim_message=lambda: claim_client_message(
                fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
            ),
        )
    )
    assert [event["type"] for event in events] == ["start", "error"]
    assert await fake_redis.exists(claim_key(user_id, chat_id, name)) == 0


@pytest.mark.asyncio
async def test_sse_client_gone_at_start_frees_the_claim(fake_redis) -> None:
    from app.modules.chat.stream_api import _stream_tokens_sse

    user_id, chat_id, name = uuid4(), uuid4(), uuid4()
    factory = MagicMock()
    body = cast(
        AsyncGenerator[str, None],
        _stream_tokens_sse(
            chat_id=chat_id,
            stream_factory=factory,
            request=_request(),
            claim_message=lambda: claim_client_message(
                fake_redis, user_id=user_id, chat_id=chat_id, client_message_id=name
            ),
        ),
    )
    assert json.loads((await anext(body)).removeprefix("data: ")) == {"type": "start"}
    await body.aclose()
    factory.assert_not_called()
    assert await fake_redis.exists(claim_key(user_id, chat_id, name)) == 0
