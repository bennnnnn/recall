"""Ping a pooled Postgres connection only after it sat idle, not on every checkout.

``pool_pre_ping`` pinged on every checkout, and SQLAlchemy's asyncpg dialect wraps each
ping in its own ``BEGIN``/``ROLLBACK`` (for PgBouncer's transaction mode): three of a
read session's six round trips were the ping, ~35 ms each turn paid several times over
before the first token. A connection used seconds ago is alive; one idle long enough
for Neon or its pooler to have dropped it is pinged, and a failed ping makes the pool
discard it and connect again.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DisconnectionError

IDLE_PING_AFTER_SECONDS = 30.0
_CHECKED_IN_AT = "recall_checked_in_at"
_now = time.monotonic


def install_idle_ping(
    engine: Engine, *, idle_after_seconds: float = IDLE_PING_AFTER_SECONDS
) -> None:
    """Ping on checkout only a connection idle ``idle_after_seconds`` or more."""

    @event.listens_for(engine.pool, "checkin")
    def _stamp(_dbapi_connection: Any, record: Any) -> None:
        record.info[_CHECKED_IN_AT] = _now()

    @event.listens_for(engine.pool, "checkout")
    def _ping_if_idle(dbapi_connection: Any, record: Any, _proxy: Any) -> None:
        checked_in_at = record.info.get(_CHECKED_IN_AT)
        if checked_in_at is None or _now() - checked_in_at < idle_after_seconds:
            return
        try:
            engine.dialect.do_ping(dbapi_connection)
        except Exception as exc:
            # The pool discards this connection and retries the checkout with a new one.
            raise DisconnectionError("pooled connection failed its idle ping") from exc
