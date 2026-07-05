"""Tests for app.repositories.push_tokens."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_for_users_returns_empty_without_querying(fake_session):
    from app.repositories.push_tokens import list_for_users

    result = await list_for_users(fake_session, [])

    assert result == []
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_list_for_users_issues_a_single_batched_query(fake_session):
    from app.repositories.push_tokens import list_for_users

    tokens = [MagicMock(), MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=tokens)))
    )

    result = await list_for_users(fake_session, [uuid4(), uuid4()])

    assert result == tokens
    fake_session.execute.assert_awaited_once()
