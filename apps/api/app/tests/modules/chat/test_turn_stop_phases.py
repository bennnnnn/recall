"""Stop at each phase of a real turn, over the socket and over SSE.

The real chat path end to end: auth, the turn, the mock model, the database and
(fake) Redis. A Stop must never take back the message the phone still shows, must
still hand the phone the saved reply's ``done``, and leaves the chat free with its
quota settled once.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from starlette.websockets import WebSocket

from app.core import access_tokens, user_cache
from app.core import redis as core_redis
from app.core.background_tasks import drain_background_tasks
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.gateways import mock_llm, storage_gateway
from app.models.orm import Message, User
from app.modules.chat import finalize_registry, stream_entry, ws_api
from app.repositories import usage as usage_repo
from app.services.quota import get_daily_usage, utc_today

_REPLY = [f"w{i}" for i in range(12)]


@dataclass
class _Socket:
    """The app's chat WebSocket, served in this event loop."""

    inbox: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    outbox: asyncio.Queue[MutableMapping[str, Any]] = field(default_factory=asyncio.Queue)
    frames: list[dict[str, Any]] = field(default_factory=list)
    served: asyncio.Task[None] | None = None

    async def receive(self) -> dict[str, Any]:
        return await self.inbox.get()

    async def send(self, message: MutableMapping[str, Any]) -> None:
        if message["type"] == "websocket.send":
            self.frames.append(json.loads(message["text"]))
        await self.outbox.put(message)

    def put(self, frame: dict[str, Any]) -> None:
        self.inbox.put_nowait({"type": "websocket.receive", "text": json.dumps(frame)})

    async def until(self, kind: str) -> dict[str, Any]:
        async with asyncio.timeout(10):
            while True:
                message = await self.outbox.get()
                if (
                    message["type"] == "websocket.send"
                    and (frame := json.loads(message["text"])).get("type") == kind
                ):
                    return frame

    async def close(self) -> None:
        self.inbox.put_nowait({"type": "websocket.disconnect", "code": 1000})
        assert self.served is not None
        async with asyncio.timeout(10):
            await self.served

    def kinds(self) -> list[str]:
        return [f["type"] for f in self.frames if f["type"] not in ("keepalive", "status")]


@dataclass
class _Chat:
    app: Any
    client: httpx.AsyncClient
    token: str
    user_id: UUID
    chat_id: UUID = field(default_factory=uuid4)

    async def open(self) -> None:
        created = await self.client.post(
            "/chats", json={}, headers={"Authorization": f"Bearer {self.token}"}
        )
        self.chat_id = UUID(created.json()["id"])
        await drain_background_tasks()

    async def socket(self) -> _Socket:
        sock = _Socket()
        scope = {
            "type": "websocket",
            "path": f"/ws/chats/{self.chat_id}",
            "headers": [(b"host", b"test")],
            "query_string": b"",
            "client": ("127.0.0.1", 50_000),
            "server": ("test", 80),
            "subprotocols": [],
        }
        websocket = WebSocket(scope, sock.receive, sock.send)
        sock.served = asyncio.create_task(ws_api.chat_websocket(websocket, self.chat_id))
        sock.inbox.put_nowait({"type": "websocket.connect"})
        sock.put({"token": self.token})
        async with asyncio.timeout(10):
            assert (await sock.outbox.get())["type"] == "websocket.accept"
        return sock

    async def sse(self, content: str, *, leave: asyncio.Event) -> list[dict[str, Any]]:
        """Send over SSE at uvicorn's ASGI spec; the client leaves once ``leave`` is set."""
        body = json.dumps({"content": content, "client_message_id": str(uuid4())}).encode()
        events: list[dict[str, Any]] = []
        pending = b""
        asked = False

        async def receive() -> dict[str, Any]:
            nonlocal asked
            if not asked:
                asked = True
                return {"type": "http.request", "body": body, "more_body": False}
            await leave.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            nonlocal pending
            pending += message.get("body", b"") if message["type"] == "http.response.body" else b""
            while b"\n\n" in pending:
                line, pending = pending.split(b"\n\n", 1)
                events.append(json.loads(line.removeprefix(b"data: ")))

        path = f"/chats/{self.chat_id}/messages/stream"
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"test"),
                (b"content-type", b"application/json"),
                (b"authorization", f"Bearer {self.token}".encode()),
            ],
            "client": ("127.0.0.1", 50_000),
            "server": ("test", 80),
        }
        await asyncio.wait_for(self.app(scope, receive, send), 10)
        return events

    async def rows(self) -> list[tuple[str, str, str | None]]:
        await drain_background_tasks()
        async with SessionLocal() as session:
            result = await session.execute(
                select(Message.role, Message.content, Message.completion)
                .where(Message.chat_id == self.chat_id)
                .order_by(Message.created_at)
            )
            return [(role, content, completion) for role, content, completion in result.all()]

    async def settled(self) -> tuple[int, int, bool]:
        """Today's usage in Redis and in the database, and whether the chat is still locked."""
        redis = core_redis.get_redis_client()
        async with SessionLocal() as session:
            in_db = await usage_repo.get_total_for_date(session, self.user_id, utc_today())
        locked = bool(await redis.exists(f"chatprep:{self.chat_id}"))
        return await get_daily_usage(redis, str(self.user_id)), in_db, locked


@pytest.fixture
async def chat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, user_generation_redis: Any
) -> AsyncIterator[_Chat]:
    from app.main import create_app

    monkeypatch.setenv("MOCK_LLM_ENABLED", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    storage_gateway._gateway_cache = None
    settings = get_settings()
    core_redis.get_redis_client.cache_clear()
    core_redis.get_jobs_redis_client.cache_clear()
    monkeypatch.setattr(core_redis, "_connect", lambda *_a, **_k: user_generation_redis)
    await engine.dispose(close=False)

    async def reply(text: str | None = None, *, messages: Any = None) -> AsyncIterator[str]:
        for word in _REPLY:
            yield word + " "
            await asyncio.sleep(0.01)

    monkeypatch.setattr(mock_llm, "mock_stream", reply)
    async with SessionLocal() as session:
        user = User(email=f"{uuid4()}@example.com", name="Stop", google_sub=str(uuid4()))
        session.add(user)
        await session.commit()
        user_id = user.id
    token = access_tokens.create_access_token(user_id, settings, session_id=str(uuid4()))
    app = create_app()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            opened = _Chat(app, client, token, user_id)
            await opened.open()
            yield opened
    finally:
        await drain_background_tasks()
        from app.modules.account import lifecycle

        async with SessionLocal() as session:
            await lifecycle.erase_user_rows(session, user_id)
        user_cache.forget_user(user_id)
        await engine.dispose(close=False)
        core_redis.get_redis_client.cache_clear()
        get_settings.cache_clear()
        storage_gateway._gateway_cache = None


def _held_load(monkeypatch: pytest.MonkeyPatch) -> tuple[asyncio.Event, asyncio.Event]:
    """The turn waits at its first read until released: a Stop lands before its message saves.

    In production that read is a few Neon round trips (and a file's text, for a turn
    with an attachment), long enough for a Stop tapped right after Send.
    """
    reached, release = asyncio.Event(), asyncio.Event()
    load = stream_entry.load_new_turn

    async def held(*args: Any, **kwargs: Any) -> Any:
        reached.set()
        await release.wait()
        return await load(*args, **kwargs)

    monkeypatch.setattr(stream_entry, "load_new_turn", held)
    return reached, release


def _message(content: str) -> dict[str, Any]:
    return {"type": "message", "content": content, "client_message_id": str(uuid4())}


async def test_ws_stop_before_the_message_saves_keeps_the_message(
    chat: _Chat, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a Stop right after Send cancelled the turn before the user's row
    was written. The phone kept the bubble, and a reload had no such message."""
    reached, release = _held_load(monkeypatch)
    sock = await chat.socket()
    sock.put(_message("Explain black holes"))
    await sock.until("start")
    await reached.wait()
    sock.put({"type": "cancel", "shown_chars": 0})
    await asyncio.sleep(0.05)
    release.set()
    await finalize_registry.wait_for_inflight_stream(chat.chat_id)

    assert await chat.rows() == [("user", "Explain black holes", None)]
    assert sock.kinds() == ["start"]
    assert await chat.settled() == (0, 0, False)
    await sock.close()


async def test_sse_client_gone_before_the_message_saves_keeps_the_message(
    chat: _Chat, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Over SSE the client stops by leaving: its message stays as on the socket."""
    reached, release = _held_load(monkeypatch)
    leave = asyncio.Event()

    async def stop_then_release() -> None:
        await reached.wait()
        leave.set()
        await asyncio.sleep(0.05)
        release.set()

    stopping = asyncio.create_task(stop_then_release())
    events = await chat.sse("Explain black holes", leave=leave)
    await stopping

    assert [event["type"] for event in events] == ["start"]
    assert await chat.rows() == [("user", "Explain black holes", None)]
    assert await chat.settled() == (0, 0, False)
