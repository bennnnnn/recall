"""Check a pooled Postgres connection on checkout only when it may have died idle.

``pool_pre_ping`` pinged on every checkout: with asyncpg that is BEGIN, ``;`` and
ROLLBACK, three round trips (about 36 ms from Fly to Neon) before a session's
first query, and a chat turn opens several sessions before the model is called.
A connection used moments ago is almost always alive, so on checkout:

- one the server already closed (Neon suspending the compute, a pooler or Postgres
  restart, ``pg_terminate_backend``) is replaced at no cost: asyncpg saw the close.
  So is one opened on another event loop, which cannot be used on this one (each
  ``TestClient`` request runs on a new loop; the app itself has one);
- one idle for ``idle_ping_seconds`` or longer is pinged first, as pre-ping did,
  since it may have been dropped without a word (a NAT or proxy idle timeout); a
  failed ping recycles the whole pool, as pre-ping's did;
- any other is trusted. If it died silently anyway, its first statement fails,
  SQLAlchemy recycles every connection older than the failure, and the request
  answers 503 + Retry-After (``core/unavailable``), which clients retry.

The pool also hands out the connection returned last (``pool_use_lifo`` in
``core/db``), so busy connections stay warm and spare ones age into the ping or
the recycle instead of every connection taking turns.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import event, exc
from sqlalchemy.engine import Engine
from sqlalchemy.pool import ConnectionPoolEntry, PoolProxiedConnection

_CHECKED_IN_AT = "checked_in_at"


def server_closed(driver_connection: Any) -> bool:
    """True when the driver already knows the server ended this connection."""
    is_closed = getattr(driver_connection, "is_closed", None)
    return bool(is_closed()) if callable(is_closed) else False


def opened_on_another_loop(driver_connection: Any) -> bool:
    """True for an asyncpg connection bound to an event loop other than the running one."""
    loop = getattr(driver_connection, "_loop", None)
    try:
        return loop is not None and loop is not asyncio.get_running_loop()
    except RuntimeError:  # no running loop: nothing to compare with
        return False


def install(engine: Engine, *, idle_ping_seconds: float) -> None:
    """Check ``engine``'s connections on checkout as above; 0 pings every reuse."""
    dialect = engine.dialect

    @event.listens_for(engine, "checkin")
    def _note_checkin(_dbapi_connection: Any, record: ConnectionPoolEntry) -> None:
        record.info[_CHECKED_IN_AT] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _check_liveness(
        dbapi_connection: Any, record: ConnectionPoolEntry, _proxy: PoolProxiedConnection
    ) -> None:
        driver = record.driver_connection
        if server_closed(driver) or opened_on_another_loop(driver):
            raise exc.DisconnectionError("Pooled connection can no longer be used")
        checked_in_at = record.info.get(_CHECKED_IN_AT)
        if checked_in_at is None or time.monotonic() - checked_in_at < idle_ping_seconds:
            # Just opened, or used moments ago.
            return
        try:
            dialect.do_ping(dbapi_connection)
        except dialect.loaded_dbapi.Error as error:
            if dialect.is_disconnect(error, dbapi_connection, None):
                raise exc.InvalidatePoolError("Ping after idle failed") from error
            raise
