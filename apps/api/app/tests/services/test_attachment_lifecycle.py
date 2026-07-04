"""Attachment lifecycle service tests."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import attachment_lifecycle


@pytest.mark.asyncio
async def test_purge_attachments_for_messages_deletes_bytes_and_rows():
    settings = Settings()
    message_id = uuid4()
    row = MagicMock()
    row.id = uuid4()
    row.storage_key = "user/file"
    session = AsyncMock()
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_for_message_ids",
            AsyncMock(return_value=[row]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_rows",
            AsyncMock(return_value=1),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_messages(
            session, settings, [message_id]
        )

    assert deleted == 1
    gateway.delete_bytes.assert_awaited_once_with("user/file")


@pytest.mark.asyncio
async def test_reap_orphan_attachments_skips_rows_linked_after_list():
    settings = Settings()
    orphan_id = uuid4()
    orphan = MagicMock()
    orphan.id = orphan_id
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[orphan]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            AsyncMock(return_value=[]),
        ) as delete_unlinked,
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 0
    delete_unlinked.assert_awaited_once()
    gateway.delete_bytes.assert_not_awaited()
