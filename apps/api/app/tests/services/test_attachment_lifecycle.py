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
    """Storage bytes are deleted BEFORE the DB unlink check (storage-first), so
    even if a row gets linked between list and delete, its bytes were already
    reaped — the DB row just isn't removed (the link wins). This is the safer
    ordering: a failed storage delete leaves a retriable DB row instead of an
    unrecoverable orphaned R2 object."""
    settings = Settings()
    orphan_id = uuid4()
    orphan = MagicMock()
    orphan.id = orphan_id
    orphan.storage_key = "user/file"
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
    # Storage-first: bytes are reaped regardless of the post-list link state.
    gateway.delete_bytes.assert_awaited_once_with("user/file")


@pytest.mark.asyncio
async def test_reap_orphan_attachments_deletes_bytes_before_db_rows():
    """The reaper must delete storage bytes BEFORE DB rows so a storage-delete
    failure (or crash mid-loop) leaves a retriable DB row, not an orphaned R2
    object the reaper can no longer discover."""
    settings = Settings()
    orphan = MagicMock()
    orphan.id = uuid4()
    orphan.storage_key = "user/file"
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    call_order: list[str] = []

    async def _delete_bytes(key):
        call_order.append("bytes")

    async def _delete_unlinked(session, ids):
        call_order.append("db")
        return [orphan.storage_key]

    gateway.delete_bytes = _delete_bytes
    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[orphan]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            side_effect=_delete_unlinked,
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 1
    assert call_order == ["bytes", "db"]


@pytest.mark.asyncio
async def test_reap_orphan_attachments_no_orphans_is_noop():
    settings = Settings()
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            AsyncMock(),
        ) as delete_unlinked,
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 0
    delete_unlinked.assert_not_awaited()
    gateway.delete_bytes.assert_not_awaited()
