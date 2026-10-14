"""Each push kind has its own switch under the master one."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.modules.notifications import push as push_service


def _where_sql(session: AsyncMock) -> str:
    """The first query the processor ran, as Postgres SQL."""
    statement = session.execute.await_args_list[0].args[0]
    return str(statement.compile(dialect=postgresql.dialect()))


def _empty_session() -> AsyncMock:
    session = AsyncMock()
    rows = MagicMock(all=MagicMock(return_value=[]))
    rows.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=rows)
    return session


@pytest.mark.parametrize(
    "process, column",
    [
        (push_service.process_todo_reminders, "push_reminders_enabled"),
        (push_service.process_email_suggestions, "push_email_suggestions_enabled"),
    ],
)
@pytest.mark.asyncio
async def test_push_kind_needs_its_own_switch(process, column) -> None:
    session = _empty_session()
    assert await process(session) == []
    sql = _where_sql(session)
    assert "users.push_notifications_enabled IS true" in sql
    assert f"users.{column} IS true" in sql


@pytest.mark.asyncio
async def test_calendar_nudges_need_the_calendar_switch() -> None:
    session = _empty_session()
    settings = Settings(calendar_nudge_enabled=True, google_calendar_enabled=True)
    with patch.object(push_service.google_calendar_gateway, "is_configured", return_value=True):
        assert await push_service.process_calendar_nudges(session, AsyncMock(), settings) == []
    sql = _where_sql(session)
    assert "users.push_notifications_enabled IS true" in sql
    assert "users.push_calendar_enabled IS true" in sql
