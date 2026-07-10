"""Tests for app.repositories.users with mocked AsyncSession."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def fake_session():
    """Return a mocked AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_get_by_id_returns_user(fake_session):
    """get_by_id should return the user from session.get."""
    from app.repositories.users import get_by_id

    user_id = uuid4()
    fake_user = MagicMock()
    fake_session.get.return_value = fake_user

    result = await get_by_id(fake_session, user_id)

    assert result is fake_user
    fake_session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_none(fake_session):
    """get_by_id should return None when user does not exist."""
    from app.repositories.users import get_by_id

    fake_session.get.return_value = None

    result = await get_by_id(fake_session, uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_create_user(fake_session):
    """create should add, commit, refresh, and return the user."""
    from app.repositories.users import create

    await create(
        fake_session,
        google_sub="sub123",
        email="test@example.com",
        name="Test",
        avatar_url=None,
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_applies_explicit_none():
    """Explicit None must clear nullable fields (omit key to leave unchanged)."""
    from app.repositories.users import update

    session = AsyncMock(spec=AsyncSession)
    user = MagicMock()
    user.custom_instructions = "keep me"
    user.location = "Seattle"
    user.name = "Ada"

    await update(session, user, custom_instructions=None, location=None)

    assert user.custom_instructions is None
    assert user.location is None
    assert user.name == "Ada"
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_delete_user_deletes_all_related(fake_session):
    """delete_user should delete messages, memories, usage, chats, and the user."""
    from app.repositories.users import delete_user

    user_id = uuid4()
    fake_user = MagicMock()
    fake_session.get.return_value = fake_user

    fake_session.execute.return_value = MagicMock(spec=CursorResult)

    await delete_user(fake_session, user_id)

    # Should execute 4 deletes + get + delete user
    assert fake_session.execute.await_count >= 4
    fake_session.delete.assert_awaited_once_with(fake_user)
    fake_session.commit.assert_awaited_once()
