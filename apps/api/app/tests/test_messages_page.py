"""Tests for paginated message listing."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import messages as messages_repo


def _msg(content: str, created_at: int):
    m = MagicMock()
    m.content = content
    m.created_at = created_at
    return m


@pytest.mark.asyncio
async def test_list_page_initial_returns_newest_chronological():
    session = AsyncMock()
    rows = [_msg("b", 2), _msg("a", 1)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)

    msgs, has_more = await messages_repo.list_page(session, uuid4(), limit=2)
    assert [m.content for m in msgs] == ["a", "b"]
    assert has_more is False


@pytest.mark.asyncio
async def test_list_page_initial_has_more_when_extra_row():
    session = AsyncMock()
    rows = [_msg("c", 3), _msg("b", 2), _msg("a", 1)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)

    msgs, has_more = await messages_repo.list_page(session, uuid4(), limit=2)
    assert [m.content for m in msgs] == ["b", "c"]
    assert has_more is True
