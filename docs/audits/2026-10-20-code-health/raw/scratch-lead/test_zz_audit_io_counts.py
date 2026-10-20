"""AUDIT SCRATCH, not for commit: SQL statements and Redis commands per request.

Drives the real app (middleware, auth, routers, chat turn with the mock model) through the
``world`` fixture and records every SQL statement and Redis command each request causes,
including the background tasks it starts (finalize, post-turn enqueue, follow-ups).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
from redis.asyncio.client import Pipeline
from sqlalchemy import event

from app.core.background_tasks import drain_background_tasks
from app.core.db import engine

from .conftest import World

OUT = Path("/home/user/recall/tmp/code-audit/raw/io-counts.json")


class _Recorder:
    def __init__(self) -> None:
        self.sql: list[str] = []
        self.redis: list[str] = []


def _sql_shape(statement: str) -> str:
    text = " ".join(statement.split())
    verb = text.split(" ", 1)[0].upper()
    tables = re.findall(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_]+)", text, flags=re.I)
    return f"{verb} {'/'.join(dict.fromkeys(t.lower() for t in tables)) or '-'}"


@pytest.fixture
def recorder(world: World, monkeypatch: pytest.MonkeyPatch):
    rec = _Recorder()

    def before(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
        rec.sql.append(_sql_shape(statement))

    event.listen(engine.sync_engine, "before_cursor_execute", before)
    fake_cls = type(world.redis)
    original = fake_cls.execute_command

    async def counting(self, *args, **kwargs):  # noqa: ANN001, ANN202
        key = str(args[1])[:40] if len(args) > 1 else ""
        rec.redis.append(f"{args[0]} {re.sub(r'[0-9a-f-]{36}', '<id>', key)}")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(fake_cls, "execute_command", counting)
    original_exec = Pipeline.execute

    async def counting_exec(self, *args, **kwargs):  # noqa: ANN001, ANN202
        names = ",".join(str(cmd[0][0]) for cmd in self.command_stack)
        rec.redis.append(f"PIPELINE[{names}]")
        return await original_exec(self, *args, **kwargs)

    monkeypatch.setattr(Pipeline, "execute", counting_exec)
    yield rec
    event.remove(engine.sync_engine, "before_cursor_execute", before)


@pytest.mark.asyncio
async def test_audit_io_counts(world: World, recorder: _Recorder, thread_sympy_executor) -> None:  # noqa: ANN001
    c, a, data = world.client, world.a, world.a_data
    chat = data.chat_id
    results: dict[str, dict] = {}

    async def measure(label: str, method: str, path: str, body: dict | None = None) -> None:
        await drain_background_tasks()
        recorder.sql.clear()
        recorder.redis.clear()
        response = await c.request(method, path, json=body, headers=a.headers)
        await drain_background_tasks()
        results[label] = {
            "status": response.status_code,
            "sql_total": len(recorder.sql),
            "sql": dict(Counter(recorder.sql).most_common()),
            "redis_total": len(recorder.redis),
            "redis": dict(Counter(recorder.redis).most_common()),
            "events": [
                json.loads(line[6:]).get("type")
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ][-4:],
        }

    await measure("GET /auth/me (cold user cache)", "GET", "/auth/me")
    await measure("GET /auth/me (warm)", "GET", "/auth/me")
    await measure("GET /chats", "GET", "/chats")
    await measure("GET /chats/{id}/messages", "GET", f"/chats/{chat}/messages")
    await measure("GET /home", "GET", "/home")
    await measure("GET /models", "GET", "/models")
    await measure("GET /memories", "GET", "/memories")
    await measure("GET /memories/documents", "GET", "/memories/documents")
    await measure("GET /todos", "GET", "/todos")
    await measure("GET /billing/plans", "GET", "/billing/plans")
    await measure("GET /attachments", "GET", "/attachments")
    await measure(
        "SSE turn 1: plain text",
        "POST",
        f"/chats/{chat}/messages/stream",
        {"content": "What should I cook tonight with rice and beans?"},
    )
    await measure(
        "SSE turn 2: plain text (warm)",
        "POST",
        f"/chats/{chat}/messages/stream",
        {"content": "And something quick for lunch tomorrow?"},
    )
    await measure(
        "SSE turn 3: maths",
        "POST",
        f"/chats/{chat}/messages/stream",
        {"content": "Solve 2x + 3 = 11"},
    )
    await measure(
        "SSE regenerate", "POST", f"/chats/{chat}/regenerate/stream", {"content": ""}
    )
    OUT.write_text(json.dumps(results, indent=2))


@pytest.mark.asyncio
async def test_audit_pool_during_stream(
    world: World, monkeypatch: pytest.MonkeyPatch, thread_sympy_executor  # noqa: ANN001
) -> None:
    """Connections checked out of the pool while the reply streams (first token)."""
    from app.core import user_cache
    from app.gateways import mock_llm

    seen: list[dict] = []
    original = mock_llm.mock_stream

    async def recording_stream(text=None, *, messages=None):  # noqa: ANN001, ANN202
        first = True
        async for token in original(text, messages=messages):
            if first:
                pool = engine.sync_engine.pool
                seen.append({"checked_out": pool.checkedout(), "status": pool.status()})
                first = False
            yield token

    monkeypatch.setattr(mock_llm, "mock_stream", recording_stream)
    c, a, data = world.client, world.a, world.a_data
    runs = []
    for label, cold in (
        ("cold user cache", True),
        ("warm user cache", False),
        ("cold user cache again", True),
    ):
        await drain_background_tasks()
        if cold:
            user_cache.forget_user(a.id)
        before = engine.sync_engine.pool.checkedout()
        response = await c.post(
            f"/chats/{data.chat_id}/messages/stream",
            json={"content": f"Give me one idea for dinner ({label})"},
            headers=a.headers,
        )
        await drain_background_tasks()
        runs.append(
            {
                "label": label,
                "status": response.status_code,
                "checked_out_before": before,
                "at_first_token": seen[-1] if seen else None,
                "after": engine.sync_engine.pool.checkedout(),
            }
        )
    Path("/home/user/recall/tmp/code-audit/raw/pool-during-stream.json").write_text(
        json.dumps(runs, indent=2)
    )


@pytest.mark.asyncio
async def test_audit_sql_text(world: World, thread_sympy_executor) -> None:  # noqa: ANN001
    """Full SQL text for one warm plain turn and one regenerate."""
    c, a, data = world.client, world.a, world.a_data
    statements: list[str] = []

    def before(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
        statements.append(" ".join(statement.split())[:400])

    out = {}
    await c.post(
        f"/chats/{data.chat_id}/messages/stream",
        json={"content": "warm up"},
        headers=a.headers,
    )
    await drain_background_tasks()
    event.listen(engine.sync_engine, "before_cursor_execute", before)
    try:
        for label, path, body in (
            ("plain turn", f"/chats/{data.chat_id}/messages/stream", {"content": "Any tips?"}),
            ("regenerate", f"/chats/{data.chat_id}/regenerate/stream", {"content": ""}),
        ):
            statements.clear()
            await c.post(path, json=body, headers=a.headers)
            await drain_background_tasks()
            out[label] = list(statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before)
    Path("/home/user/recall/tmp/code-audit/raw/sql-text.json").write_text(json.dumps(out, indent=2))


@pytest.mark.asyncio
async def test_audit_idle_in_transaction_during_stream(
    world: World, monkeypatch: pytest.MonkeyPatch, thread_sympy_executor  # noqa: ANN001
) -> None:
    """Backends idle in a transaction while the reply streams (cold vs warm user cache)."""
    import asyncpg

    from app.core import user_cache
    from app.gateways import mock_llm

    seen: list[list] = []
    original = mock_llm.mock_stream

    async def recording_stream(text=None, *, messages=None):  # noqa: ANN001, ANN202
        first = True
        async for token in original(text, messages=messages):
            if first:
                conn = await asyncpg.connect(
                    "postgresql://postgres:postgres@127.0.0.1:5432/recall_cleanup"
                )
                try:
                    rows = await conn.fetch(
                        "SELECT state, left(query, 80) AS q FROM pg_stat_activity "
                        "WHERE datname = 'recall_cleanup' AND pid <> pg_backend_pid() "
                        "AND state <> 'idle'"
                    )
                finally:
                    await conn.close()
                seen.append([dict(r) for r in rows])
                first = False
            yield token

    monkeypatch.setattr(mock_llm, "mock_stream", recording_stream)
    c, a, data = world.client, world.a, world.a_data
    runs = {}
    for label, cold in (("cold", True), ("warm", False)):
        await drain_background_tasks()
        if cold:
            user_cache.forget_user(a.id)
        await c.post(
            f"/chats/{data.chat_id}/messages/stream",
            json={"content": f"One dinner idea ({label})"},
            headers=a.headers,
        )
        await drain_background_tasks()
        runs[label] = seen[-1] if seen else None
    Path("/home/user/recall/tmp/code-audit/raw/idle-in-transaction.json").write_text(
        json.dumps(runs, indent=2, default=str)
    )


@pytest.mark.asyncio
async def test_audit_wire_roundtrips(
    world: World, monkeypatch: pytest.MonkeyPatch, thread_sympy_executor  # noqa: ANN001
) -> None:
    """Pool checkouts and asyncpg BEGIN/;/ROLLBACK/COMMIT per warm plain turn."""
    import collections

    import asyncpg

    calls: collections.Counter[str] = collections.Counter()
    conn_cls = asyncpg.connection.Connection
    orig_execute, orig_fetchrow = conn_cls.execute, conn_cls.fetchrow

    async def execute(self, query, *a, **k):  # noqa: ANN001, ANN202
        calls[query.strip().split()[0].rstrip(";").upper() or "?"] += 1
        return await orig_execute(self, query, *a, **k)

    async def fetchrow(self, query, *a, **k):  # noqa: ANN001, ANN202
        calls["PING" if query.strip() == ";" else "FETCHROW"] += 1
        return await orig_fetchrow(self, query, *a, **k)

    monkeypatch.setattr(conn_cls, "execute", execute)
    monkeypatch.setattr(conn_cls, "fetchrow", fetchrow)

    def on_checkout(*_):  # noqa: ANN002, ANN202
        calls.update(["CHECKOUT"])

    def on_sql(conn, cur, stmt, *_):  # noqa: ANN001, ANN002, ANN202
        calls.update(["SQL " + stmt.split()[0]])

    event.listen(engine.sync_engine.pool, "checkout", on_checkout)
    event.listen(engine.sync_engine, "before_cursor_execute", on_sql)
    c, a, chat = world.client, world.a, world.a_data.chat_id
    out = {}
    try:
        for label, text in (("warm up", "warm up"), ("measured", "Any tips for a short walk?")):
            await drain_background_tasks()
            calls.clear()
            await c.post(f"/chats/{chat}/messages/stream", json={"content": text}, headers=a.headers)
            await drain_background_tasks()
            out[label] = dict(calls)
    finally:
        event.remove(engine.sync_engine.pool, "checkout", on_checkout)
        event.remove(engine.sync_engine, "before_cursor_execute", on_sql)
    Path("/home/user/recall/tmp/code-audit/raw/wire-roundtrips.json").write_text(
        json.dumps(out, indent=2)
    )
