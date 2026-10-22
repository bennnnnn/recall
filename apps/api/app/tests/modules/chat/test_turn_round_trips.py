"""The database and Redis round trips a chat turn makes before its reply starts.

Each one costs the user time before the first token: about 12 ms per Postgres round
trip from Fly to Neon, and about 1 ms per Redis command. This drives the real SSE
chat path (auth, rate limits, the turn, the mock model) for a few kinds of message
and counts, from the request until the first token is sent: SQL statements, pool
checkouts, transactions (each also a BEGIN and a COMMIT or ROLLBACK on the wire),
checkout pings (three round trips each; none for a connection used moments ago,
``core/pool_liveness``) and Redis round trips (a pipeline is one). That is
everything before the model is called, plus the user message's save, which the
first token waits for.

No timing: counts only, so it cannot flake. Each ceiling is the count when it was
set. A change that lowers a count lowers its ceiling here in the same change, so
it stays down. A change that raises one fails this test: make the new round trip
unnecessary, overlap it with one already made, or, when it is worth the time,
raise the ceiling and say why in the change's description.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import fakeredis.aioredis
import httpx
import pytest
import redis.asyncio as redis_asyncio
from redis.asyncio.client import Pipeline
from sqlalchemy import event

from app.core import access_tokens, user_cache
from app.core import redis as core_redis
from app.core.background_tasks import drain_background_tasks
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.gateways.storage_gateway import reset_storage_gateway_cache
from app.models.orm import Memory, TodoItem, User
from app.modules.chat import stream_api
from app.modules.images import search as image_search
from app.repositories import users as users_repo
from app.services.quota import tokens as quota_tokens


@dataclass(frozen=True)
class Ceiling:
    sql: int
    checkouts: int
    transactions: int
    redis: int
    pings: int = 0


# Measured on the SSE path with the user, the chat and today's usage already known to
# the process and to Redis, as for every message after the day's first. A new chat
# each, so the history read finds nothing; the user message's save is one of each.
# To update: ``pytest -s`` on this file prints every count.
CEILINGS: dict[str, tuple[str, Ceiling]] = {
    "greeting": ("hi", Ceiling(sql=1, checkouts=1, transactions=1, redis=16)),
    "question": (
        "What's the capital of France?",
        Ceiling(sql=2, checkouts=2, transactions=2, redis=16),
    ),
    "reminder": (
        "Remind me to call mom tomorrow at 5pm",
        Ceiling(sql=7, checkouts=7, transactions=7, redis=21),
    ),
    "memory line": (
        "Remember that I'm allergic to peanuts",
        Ceiling(sql=7, checkouts=7, transactions=7, redis=22),
    ),
    # The lookup finds no usable photo, so the model answers in words.
    "photo lookup": (
        "Show me a photo of the Eiffel Tower",
        Ceiling(sql=3, checkouts=3, transactions=3, redis=21),
    ),
}
# The day's first message: Redis has no usage counter yet, so it is read back from
# the database before the turn reserves its tokens.
FIRST_OF_THE_DAY = ("hi", Ceiling(sql=2, checkouts=2, transactions=2, redis=17))


@dataclass
class _Trips:
    counting: bool = False
    sql: int = 0
    checkouts: int = 0
    transactions: int = 0
    redis: int = 0
    pings: int = 0

    def start(self) -> None:
        self.sql = self.checkouts = self.transactions = self.redis = self.pings = 0
        self.counting = True

    def seen(self) -> Ceiling:
        return Ceiling(self.sql, self.checkouts, self.transactions, self.redis, self.pings)


@dataclass
class _Turns:
    client: httpx.AsyncClient
    headers: dict[str, str]
    redis: Any
    trips: _Trips

    async def first_token_trips(self, content: str) -> Ceiling:
        """Send ``content`` in a new chat; the round trips until its first token."""
        created = await self.client.post("/chats", json={}, headers=self.headers)
        chat_id = created.json()["id"]
        # The previous turn's save and jobs run on their own tasks: finish them first.
        await drain_background_tasks()
        self.trips.start()
        response = await self.client.post(
            f"/chats/{chat_id}/messages/stream", json={"content": content}, headers=self.headers
        )
        self.trips.counting = False
        assert response.status_code == 200
        assert '"type":"token"' in response.text, response.text[-400:]
        return self.trips.seen()


async def _seed_user() -> UUID:
    """A free account with a remembered fact and an open to-do, as a turn would read."""
    async with SessionLocal() as session:
        user = User(email=f"{uuid4()}@example.com", name="Round Trips", google_sub=str(uuid4()))
        session.add(user)
        await session.flush()
        session.add_all(
            [
                Memory(
                    user_id=user.id,
                    type="project",
                    topic="recent-work",
                    text="User is building a chat app called Recall",
                    status="active",
                ),
                TodoItem(user_id=user.id, content="buy milk", topic="Groceries", sort_order=0),
            ]
        )
        await session.commit()
        return user.id


# Set while a fallback that only fakeredis runs stands in for a Lua script.
_IN_PLACE_OF_LUA: ContextVar[bool] = ContextVar("in_place_of_lua", default=False)


def _count(trips: _Trips, field: str) -> Any:
    def record(*_args: Any, **_kwargs: Any) -> None:
        if trips.counting and not _IN_PLACE_OF_LUA.get():
            setattr(trips, field, getattr(trips, field) + 1)

    return record


@pytest.fixture
async def turns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncIterator[_Turns]:
    from app.main import create_app

    monkeypatch.setenv("MOCK_LLM_ENABLED", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    # Production runs with the global spend cap on; a turn reads it.
    monkeypatch.setenv("DAILY_GLOBAL_SPEND_USD", "1000")
    get_settings.cache_clear()
    reset_storage_gateway_cache()
    settings = get_settings()
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    core_redis.get_redis_client.cache_clear()
    monkeypatch.setattr(redis_asyncio, "from_url", lambda *_a, **_k: fake)
    await engine.dispose(close=False)

    trips = _Trips()
    listeners = [
        ("before_cursor_execute", _count(trips, "sql")),
        ("checkout", _count(trips, "checkouts")),
        ("begin", _count(trips, "transactions")),
    ]
    for name, listener in listeners:
        event.listen(engine.sync_engine, name, listener)
    dialect = engine.sync_engine.dialect
    ping = dialect.do_ping

    def counted_ping(dbapi_connection: Any) -> bool:
        _count(trips, "pings")()
        return ping(dbapi_connection)

    monkeypatch.setattr(dialect, "do_ping", counted_ping)
    # Every fake Redis counts: in production they are all the one Redis.
    fake_redis_class = type(fake)
    send = fake_redis_class.execute_command
    run_pipeline = Pipeline.execute

    async def counted_send(self: Any, *args: Any, **kwargs: Any) -> Any:
        _count(trips, "redis")()
        return await send(self, *args, **kwargs)

    async def counted_pipeline(self: Any, *args: Any, **kwargs: Any) -> Any:
        _count(trips, "redis")()
        return await run_pipeline(self, *args, **kwargs)

    monkeypatch.setattr(fake_redis_class, "execute_command", counted_send)
    monkeypatch.setattr(Pipeline, "execute", counted_pipeline)
    # fakeredis has no Lua, so the token reserve's script fails there and a WATCH
    # fallback takes the tokens. Production's Redis runs the script in the one EVAL
    # already counted: the fallback's commands are not.
    reserve_watched = quota_tokens._reserve_up_to_watched

    async def reserve_in_place_of_lua(*args: Any, **kwargs: Any) -> int:
        token = _IN_PLACE_OF_LUA.set(True)
        try:
            return await reserve_watched(*args, **kwargs)
        finally:
            _IN_PLACE_OF_LUA.reset(token)

    monkeypatch.setattr(quota_tokens, "_reserve_up_to_watched", reserve_in_place_of_lua)
    build_token_event = stream_api.build_token_event

    def first_token_stops_the_count(content: str) -> dict[str, Any]:
        trips.counting = False
        return build_token_event(content)

    monkeypatch.setattr(stream_api, "build_token_event", first_token_stops_the_count)
    # No photo is fetched from the internet: a lookup finds none it can use.
    monkeypatch.setattr(image_search, "_fetch_candidates", AsyncMock(return_value=[]))

    user_id = await _seed_user()
    token = access_tokens.create_access_token(user_id, settings, session_id=str(uuid4()))
    app = create_app()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield _Turns(client, {"Authorization": f"Bearer {token}"}, fake, trips)
    finally:
        await drain_background_tasks()
        for name, listener in listeners:
            event.remove(engine.sync_engine, name, listener)
        async with SessionLocal() as session:
            await users_repo.delete_user(session, user_id)
        user_cache.forget_user(user_id)
        await engine.dispose(close=False)
        await fake.aclose()
        core_redis.get_redis_client.cache_clear()
        get_settings.cache_clear()
        reset_storage_gateway_cache()


def _within(seen: Ceiling, ceiling: Ceiling) -> list[str]:
    return [
        f"{name}: {getattr(seen, name)} > {getattr(ceiling, name)}"
        for name in ("sql", "checkouts", "transactions", "redis", "pings")
        if getattr(seen, name) > getattr(ceiling, name)
    ]


def _over(
    seen: dict[str, Ceiling], ceilings: dict[str, tuple[str, Ceiling]]
) -> dict[str, list[str]]:
    return {kind: _within(counts, ceilings[kind][1]) for kind, counts in seen.items()}


async def test_turn_round_trips_before_the_first_token_stay_under_their_ceilings(
    turns: _Turns,
) -> None:
    # Today's usage counter now exists, as for every message after the day's first.
    await turns.first_token_trips("hello")
    seen = {kind: await turns.first_token_trips(content) for kind, (content, _) in CEILINGS.items()}
    print("round trips before the first token:", seen)

    over = {kind: problems for kind, problems in _over(seen, CEILINGS).items() if problems}
    assert not over, over


async def test_the_days_first_turn_reads_back_usage_under_its_ceiling(turns: _Turns) -> None:
    content, ceiling = FIRST_OF_THE_DAY
    for key in await turns.redis.keys("usage:*"):
        await turns.redis.delete(key)

    seen = await turns.first_token_trips(content)
    print("round trips before the day's first token:", seen)

    assert not _within(seen, ceiling), seen
