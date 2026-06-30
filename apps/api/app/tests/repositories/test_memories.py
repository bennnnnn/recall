from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import memories as memories_repo


@pytest.fixture
def fake_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_upsert_sections_empty_items_is_noop(fake_session):
    await memories_repo.upsert_sections(fake_session, user_id=uuid4(), items=[])
    fake_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_sections_executes_and_commits(fake_session):
    user_id = uuid4()
    items = [("profile", "User is Sam, a software engineer.", 0.9, None)]
    await memories_repo.upsert_sections(fake_session, user_id=user_id, items=items)
    fake_session.execute.assert_awaited_once()
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_user_returns_memories(fake_session):
    user_id = uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    fake_session.execute.return_value = mock_result
    result = await memories_repo.list_for_user(fake_session, user_id)
    assert result == []
