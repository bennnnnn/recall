"""Tests for app.repositories.messages with mocked AsyncSession."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def fake_session():
    """Return a mocked AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_create_message(fake_session):
    """create should add, commit, refresh, and return the message."""
    from app.repositories.messages import create

    chat_id = uuid4()
    user_id = uuid4()

    _ = await create(
        fake_session,
        chat_id=chat_id,
        user_id=user_id,
        role="user",
        content="Hello",
        model="free-chat",
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_for_chat(fake_session):
    """count_for_chat should return the count of messages."""
    from app.repositories.messages import count_for_chat

    chat_id = uuid4()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    fake_session.execute.return_value = mock_result

    result = await count_for_chat(fake_session, chat_id)

    assert result == 5
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_last(fake_session):
    """get_last should return the most recent message via scalar_one_or_none."""
    from app.repositories.messages import get_last

    chat_id = uuid4()
    mock_message = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_message
    fake_session.execute.return_value = mock_result

    result = await get_last(fake_session, chat_id)

    assert result is mock_message
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_last_user(fake_session):
    """get_last_user should return the most recent user message."""
    from app.repositories.messages import get_last_user

    chat_id = uuid4()
    mock_message = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_message
    fake_session.execute.return_value = mock_result

    result = await get_last_user(fake_session, chat_id)

    assert result is mock_message
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_feedback(fake_session):
    """set_feedback should update the feedback field of a message."""
    from app.repositories.messages import set_feedback

    msg_id = uuid4()
    chat_id = uuid4()
    mock_message = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_message
    fake_session.execute.return_value = mock_result

    result = await set_feedback(fake_session, msg_id, chat_id, "like")

    assert result is mock_message
    assert mock_message.feedback == "like"
    fake_session.commit.assert_awaited_once()
