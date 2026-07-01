"""Attachment repository helper tests."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import attachments as attachments_repo


@pytest.mark.asyncio
async def test_link_to_message_updates_owned_rows():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 2
    session.execute = AsyncMock(return_value=result)

    linked = await attachments_repo.link_to_message(
        session,
        user_id=uuid4(),
        attachment_ids=[uuid4(), uuid4()],
        message_id=uuid4(),
    )

    assert linked == 2
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_orphans_returns_unlinked_old_rows():
    session = AsyncMock()
    row = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [row]
    result = MagicMock()
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)

    orphans = await attachments_repo.list_orphans(session, older_than_hours=24)

    assert orphans == [row]
    session.execute.assert_awaited_once()
