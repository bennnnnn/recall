"""Tests for app.repositories.chats with mocked AsyncSession."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def fake_session():
    """Return a mocked AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_create_chat(fake_session):
    """create should add, commit, refresh, and return the chat."""
    from app.repositories.chats import create

    await create(fake_session, user_id=uuid4(), model="free-chat")

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_chat(fake_session):
    """get_by_id should return a chat via scalar_one_or_none."""
    from app.repositories.chats import get_by_id

    mock_chat = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_chat
    fake_session.execute.return_value = mock_result

    result = await get_by_id(fake_session, uuid4(), uuid4())

    assert result is mock_chat


@pytest.mark.asyncio
async def test_list_for_user_returns_chats(fake_session):
    """list_for_user should return a list of chats with messages."""
    from app.repositories.chats import list_for_user

    mock_chat = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_chat]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await list_for_user(fake_session, uuid4())

    assert result == [mock_chat]


@pytest.mark.asyncio
async def test_delete_empty_for_user_with_no_empty_chats(fake_session):
    """delete_empty_for_user should return 0 when no empty chats exist."""
    from app.repositories.chats import delete_empty_for_user

    mock_result = MagicMock()
    mock_result.rowcount = 0
    fake_session.execute.return_value = mock_result

    result = await delete_empty_for_user(fake_session, uuid4())

    assert result == 0


@pytest.mark.asyncio
async def test_delete_by_id_returns_false_when_not_found(fake_session):
    """delete_by_id should return False when chat does not exist."""
    from app.repositories.chats import delete_by_id

    # get_by_id returns None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    fake_session.execute.return_value = mock_result

    result = await delete_by_id(fake_session, uuid4(), uuid4())

    assert result is False


@pytest.mark.asyncio
async def test_set_title(fake_session):
    """set_title should update title, commit, and refresh."""
    from app.repositories.chats import set_title

    mock_chat = MagicMock()

    _ = await set_title(fake_session, mock_chat, "New Title")

    assert mock_chat.title == "New Title"
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_pinned(fake_session):
    """set_pinned should update pinned flag, commit, and refresh."""
    from app.repositories.chats import set_pinned

    mock_chat = MagicMock()

    _ = await set_pinned(fake_session, mock_chat, True)

    assert mock_chat.pinned is True
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_touch_updates_timestamp(fake_session):
    """touch should update updated_at and commit."""
    from app.repositories.chats import touch

    mock_chat = MagicMock()

    await touch(fake_session, mock_chat)

    assert mock_chat.updated_at is not None
    fake_session.commit.assert_awaited_once()


def test_group_by_recency_today():
    """Chats updated today should be grouped under 'today'."""
    from app.repositories.chats import group_by_recency

    now = datetime.now(UTC)
    chat = MagicMock()
    chat.updated_at = now

    result = group_by_recency([chat])

    assert len(result["today"]) == 1
    assert len(result["yesterday"]) == 0
    assert len(result["last_7_days"]) == 0
    assert len(result["this_month"]) == 0
    assert len(result["older"]) == 0


def test_group_by_recency_older():
    """Chats from before this month should be grouped under 'older'."""
    from datetime import timedelta

    from app.repositories.chats import group_by_recency

    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
    old = now - timedelta(days=20)
    chat = MagicMock()
    chat.updated_at = old

    result = group_by_recency([chat], now=now)

    assert len(result["today"]) == 0
    assert len(result["older"]) == 1


def test_group_by_recency_last_7_days():
    """Chats from 2-7 days ago land in last_7_days."""
    from datetime import timedelta

    from app.repositories.chats import group_by_recency

    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
    chat = MagicMock()
    chat.updated_at = now - timedelta(days=4)

    result = group_by_recency([chat], now=now)

    assert result["today"] == []
    assert result["yesterday"] == []
    assert len(result["last_7_days"]) == 1


def test_group_by_recency_this_month():
    """Chats from earlier this month (but not last 7 days) land in this_month."""
    from datetime import timedelta

    from app.repositories.chats import group_by_recency

    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
    chat = MagicMock()
    chat.updated_at = now - timedelta(days=10)

    result = group_by_recency([chat], now=now)

    assert len(result["this_month"]) == 1


def test_group_by_recency_mixed():
    """Chats from different time periods should be split correctly."""
    from app.repositories.chats import group_by_recency

    now = datetime(2026, 6, 28, 15, 0, 0, tzinfo=UTC)
    today_chat = MagicMock()
    today_chat.updated_at = now
    yesterday_chat = MagicMock()
    yesterday_chat.updated_at = now - timedelta(hours=20)
    old_chat = MagicMock()
    old_chat.updated_at = now - timedelta(days=7)

    result = group_by_recency([today_chat, yesterday_chat, old_chat], now=now)

    assert len(result["today"]) == 1
    assert len(result["yesterday"]) == 1
    assert len(result["last_7_days"]) == 1


def test_group_by_recency_uses_user_timezone():
    """Local yesterday must not appear under Today when UTC date already rolled forward."""
    from app.repositories.chats import group_by_recency

    # Sunday 2pm in Los Angeles
    now = datetime(2026, 6, 28, 21, 0, 0, tzinfo=UTC)
    # Saturday 11pm in Los Angeles (Sunday 06:00 UTC — UTC would call this "today")
    chat = MagicMock()
    chat.updated_at = datetime(2026, 6, 28, 6, 0, 0, tzinfo=UTC)

    utc_groups = group_by_recency([chat], now=now)
    la_groups = group_by_recency([chat], user_timezone="America/Los_Angeles", now=now)

    assert len(utc_groups["today"]) == 1
    assert utc_groups["yesterday"] == []
    assert len(la_groups["yesterday"]) == 1
    assert la_groups["today"] == []
