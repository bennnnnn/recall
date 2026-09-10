from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import memories as memories_repo


@pytest.fixture
def fake_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
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
    assert fake_session.execute.await_count >= 1
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_sections_commit_false_flushes_without_committing(fake_session):
    await memories_repo.upsert_sections(
        fake_session,
        user_id=uuid4(),
        items=[("fact", "Owns a bicycle.", 0.9, None)],
        commit=False,
    )

    fake_session.execute.assert_awaited()
    fake_session.flush.assert_awaited()
    fake_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_sections_adds_duplicate_types_as_separate_facts(fake_session):
    user_id = uuid4()
    items = [
        ("profile", "Low confidence profile.", 0.5, None),
        ("profile", "High confidence profile.", 0.9, None),
        ("preference", "Likes tea.", 0.8, None),
    ]
    await memories_repo.upsert_sections(fake_session, user_id=user_id, items=items)
    assert fake_session.execute.await_count >= 1
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_sections_keeps_same_type_facts(fake_session):
    user_id = uuid4()
    items = [
        ("fact", "First fact.", 0.7, None),
        ("fact", "Second fact.", 0.7, None),
    ]
    await memories_repo.upsert_sections(fake_session, user_id=user_id, items=items)
    assert fake_session.execute.await_count >= 1
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_user_returns_memories(fake_session):
    user_id = uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    fake_session.execute.return_value = mock_result
    result = await memories_repo.list_for_user(fake_session, user_id)
    assert result == []


@pytest.mark.asyncio
async def test_has_any_embedding_true_when_row_exists(fake_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid4()
    fake_session.execute.return_value = mock_result
    assert await memories_repo.has_any_embedding(fake_session, uuid4()) is True


@pytest.mark.asyncio
async def test_has_any_embedding_false_when_empty(fake_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    fake_session.execute.return_value = mock_result
    assert await memories_repo.has_any_embedding(fake_session, uuid4()) is False
