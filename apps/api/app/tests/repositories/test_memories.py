"""Tests for app.repositories.memories with mocked AsyncSession."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def fake_session():
    """Return a mocked AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_delete_by_id_returns_true_when_row_deleted(fake_session):
    """delete_by_id returns True when at least one row is affected."""
    from app.repositories.memories import delete_by_id

    # Simulate a CursorResult with rowcount=1
    mock_result = MagicMock(spec=CursorResult)
    mock_result.rowcount = 1
    fake_session.execute.return_value = mock_result

    result = await delete_by_id(fake_session, uuid4(), uuid4())

    assert result is True
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_id_returns_false_when_no_rows(fake_session):
    """delete_by_id returns False when no rows match."""
    from app.repositories.memories import delete_by_id

    mock_result = MagicMock(spec=CursorResult)
    mock_result.rowcount = 0
    fake_session.execute.return_value = mock_result

    result = await delete_by_id(fake_session, uuid4(), uuid4())

    assert result is False


@pytest.mark.asyncio
async def test_upsert_many_empty_items_is_noop(fake_session):
    """upsert_many with empty items list should not execute anything."""
    from app.repositories.memories import upsert_many

    await upsert_many(fake_session, user_id=uuid4(), items=[])

    fake_session.execute.assert_not_called()
    fake_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_many_executes_and_commits(fake_session):
    """upsert_many with items should execute an insert and commit."""
    from app.repositories.memories import upsert_many

    user_id = uuid4()
    items: list[tuple[str, str, float, UUID | None]] = [
        ("fact", "User likes Python", 0.9, None),
        ("profile", "User is a developer", 0.95, uuid4()),
    ]

    await upsert_many(fake_session, user_id=user_id, items=items)

    fake_session.execute.assert_awaited_once()
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_user_returns_memories(fake_session):
    """list_for_user should execute a select and return scalars."""
    from app.repositories.memories import list_for_user

    user_id = uuid4()
    # Simulate a result with scalars
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await list_for_user(fake_session, user_id)

    assert result == []
    fake_session.execute.assert_awaited_once()
