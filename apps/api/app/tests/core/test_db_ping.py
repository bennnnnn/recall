"""A pooled connection is pinged only after sitting idle, and a dead one is replaced.

``pool_pre_ping`` cost three round trips (``BEGIN``, ``;``, ``ROLLBACK``) on every
checkout; most sessions run seconds apart on a warm connection.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import db_ping
from app.core.config import get_settings
from app.core.database_url import prepare_asyncpg_url


def _engine():
    url, connect_args = prepare_asyncpg_url(get_settings().database_url)
    engine = create_async_engine(url, connect_args=connect_args, pool_size=1, max_overflow=0)
    db_ping.install_idle_ping(engine.sync_engine, idle_after_seconds=30.0)
    return engine


def _later(seconds: float):
    """The idle clock, ``seconds`` ahead: every pooled connection looks that idle."""
    real_now = time.monotonic
    return patch.object(db_ping, "_now", lambda: real_now() + seconds)


async def test_a_warm_connection_is_not_pinged() -> None:
    engine = _engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        with patch.object(engine.sync_engine.dialect, "do_ping") as ping:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        ping.assert_not_called()
    finally:
        await engine.dispose()


async def test_an_idle_connection_is_pinged() -> None:
    engine = _engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        real_ping = engine.sync_engine.dialect.do_ping
        with (
            _later(60.0),
            patch.object(engine.sync_engine.dialect, "do_ping", side_effect=real_ping) as ping,
        ):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        ping.assert_called_once()
    finally:
        await engine.dispose()


async def test_an_idle_connection_the_server_dropped_is_replaced() -> None:
    engine = _engine()
    try:
        async with engine.connect() as conn:
            dropped_pid = (await conn.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        killer = _engine()
        try:
            async with killer.connect() as conn:
                await conn.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": dropped_pid})
        finally:
            await killer.dispose()
        with _later(60.0):
            async with engine.connect() as conn:
                pid = (await conn.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        assert pid != dropped_pid
    finally:
        await engine.dispose()


def test_the_app_engine_does_not_pre_ping_every_checkout() -> None:
    from app.core import db

    assert db.engine.sync_engine.pool._pre_ping is False
