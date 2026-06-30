"""Tests for app.repositories.attachments."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_pending_attachment(fake_session):
    from app.repositories.attachments import create_pending

    attachment_id = uuid4()
    row = await create_pending(
        fake_session,
        attachment_id=attachment_id,
        user_id=uuid4(),
        storage_key="uploads/a",
        content_type="image/png",
        size_bytes=128,
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    assert row.id == attachment_id


@pytest.mark.asyncio
async def test_get_by_id_returns_attachment(fake_session):
    from app.repositories.attachments import get_by_id

    mock_row = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=mock_row)
    )

    result = await get_by_id(fake_session, uuid4(), uuid4())

    assert result is mock_row


@pytest.mark.asyncio
async def test_link_message_sets_message_id(fake_session):
    from app.repositories.attachments import link_message

    row = MagicMock()
    message_id = uuid4()

    linked = await link_message(fake_session, row, message_id)

    assert linked.message_id == message_id
    fake_session.commit.assert_awaited_once()
