"""Pooled connections are checked on checkout only when they may have died (core/pool_liveness).

``pool_pre_ping`` spent three round trips (BEGIN, ``;``, ROLLBACK) before the first
query of every session. Now a connection the server closed is replaced without a
round trip, one idle past the threshold is pinged first, and one used moments ago
is trusted. These run against the test Postgres, where ``pg_terminate_backend``
ends a pooled connection the way Neon suspending its compute or a restart does.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import asyncpg
import pytest
from sqlalchemy import exc, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core import pool_liveness
from app.core.config import get_settings
from app.core.database_url import prepare_asyncpg_url


def _engine(*, idle_ping_seconds: float | None) -> AsyncEngine:
    """One pooled connection, so every query reuses it; None leaves the check out."""
    url, connect_args = prepare_asyncpg_url(get_settings().database_url)
    engine = create_async_engine(
        url, connect_args=connect_args, pool_size=1, max_overflow=0, pool_use_lifo=True
    )
    if idle_ping_seconds is not None:
        pool_liveness.install(engine.sync_engine, idle_ping_seconds=idle_ping_seconds)
    return engine


@pytest.fixture
async def engines() -> AsyncIterator[Callable[..., AsyncEngine]]:
    made: list[AsyncEngine] = []

    def make(*, idle_ping_seconds: float | None) -> AsyncEngine:
        made.append(_engine(idle_ping_seconds=idle_ping_seconds))
        return made[-1]

    yield make
    for engine in made:
        await engine.dispose()


def _pings(engine: AsyncEngine) -> list[Any]:
    """Every liveness ping ``engine`` sends from here on."""
    sent: list[Any] = []
    dialect = engine.sync_engine.dialect
    ping = dialect.do_ping

    def counting(dbapi_connection: Any) -> bool:
        sent.append(dbapi_connection)
        return ping(dbapi_connection)

    dialect.do_ping = counting  # type: ignore[method-assign]
    return sent


async def _backend(engine: AsyncEngine) -> tuple[int, Any]:
    """The server process behind the pooled connection, and its asyncpg connection."""
    async with engine.connect() as conn:
        pid = int((await conn.execute(text("SELECT pg_backend_pid()"))).scalar_one())
        raw = await conn.get_raw_connection()
        return pid, raw.driver_connection


async def _end_on_the_server(pid: int, driver: Any) -> None:
    """Terminate the backend from another connection and wait until asyncpg sees it."""
    dsn = make_url(get_settings().database_url).set(drivername="postgresql")
    killer = await asyncpg.connect(dsn.render_as_string(hide_password=False))
    try:
        await killer.execute("SELECT pg_terminate_backend($1)", pid)
    finally:
        await killer.close()
    for _ in range(100):
        if driver.is_closed():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("asyncpg never saw the server close the connection")


async def test_a_connection_the_server_closed_is_replaced_without_a_round_trip(engines) -> None:
    engine = engines(idle_ping_seconds=60)
    pings = _pings(engine)
    first, driver = await _backend(engine)
    await _end_on_the_server(first, driver)

    second, _ = await _backend(engine)

    assert second != first
    assert pings == []


async def test_without_the_check_a_closed_pooled_connection_fails_the_next_query(engines) -> None:
    """Why the check exists: with neither pre-ping nor it, the dead connection is used."""
    engine = engines(idle_ping_seconds=None)
    first, driver = await _backend(engine)
    await _end_on_the_server(first, driver)

    with pytest.raises(exc.DBAPIError):
        await _backend(engine)


async def test_a_connection_used_moments_ago_is_trusted_without_a_ping(engines) -> None:
    engine = engines(idle_ping_seconds=60)
    pings = _pings(engine)

    pids = [(await _backend(engine))[0] for _ in range(3)]

    assert len(set(pids)) == 1
    assert pings == []


async def test_a_connection_idle_past_the_threshold_is_pinged_first(engines) -> None:
    engine = engines(idle_ping_seconds=0.05)
    pings = _pings(engine)
    first, _ = await _backend(engine)
    await asyncio.sleep(0.1)

    second, _ = await _backend(engine)

    assert second == first
    assert len(pings) == 1


async def test_a_silently_dropped_idle_connection_fails_its_ping_and_is_replaced(
    engines, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = engines(idle_ping_seconds=0)
    pings = _pings(engine)
    first, driver = await _backend(engine)
    await _end_on_the_server(first, driver)
    # A drop the driver never heard about (a NAT or proxy idle timeout).
    monkeypatch.setattr(pool_liveness, "server_closed", lambda _driver: False)

    second, _ = await _backend(engine)

    assert second != first
    assert len(pings) == 1


def test_a_connection_opened_on_another_event_loop_is_replaced() -> None:
    """Each TestClient request runs on a new loop; pre-ping used to catch this too."""
    engine = _engine(idle_ping_seconds=60)
    try:
        first, _ = asyncio.run(_backend(engine))
        second, _ = asyncio.run(_backend(engine))
    finally:
        # The pooled connection's loop is gone: drop it rather than close it there.
        asyncio.run(engine.dispose(close=False))

    assert second != first


def test_the_app_engine_checks_liveness_instead_of_pinging_every_checkout() -> None:
    from app.core import db

    pool = db.engine.sync_engine.pool
    assert pool._pre_ping is False
    assert pool.dispatch.checkout
    assert get_settings().db_idle_ping_seconds > 0
