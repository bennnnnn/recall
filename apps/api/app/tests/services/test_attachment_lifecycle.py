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
    order: list[str] = []

    async def delete_rows(_session, ids, *, commit=True):
        order.append("rows")
        return 1

    async def delete_bytes(key: str) -> None:
        order.append(f"bytes:{key}")

    gateway.delete_bytes = delete_bytes

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_for_message_ids",
            AsyncMock(return_value=[row]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_rows",
            side_effect=delete_rows,
        ),
        patch(
            "app.repositories.attachment_chunks.delete_for_attachment_ids",
            AsyncMock(),
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
    assert order == ["rows", "bytes:user/file"]


@pytest.mark.asyncio
async def test_purge_attachments_for_user_deletes_bytes_before_rows():
    settings = Settings()
    user_id = uuid4()
    row = MagicMock()
    row.id = uuid4()
    row.storage_key = "user/acct-file"
    session = AsyncMock()
    order: list[str] = []

    async def delete_bytes(key: str) -> None:
        order.append(f"bytes:{key}")

    async def delete_rows(_session, ids):
        order.append(f"rows:{ids[0]}")
        return 1

    gateway = MagicMock()
    gateway.delete_bytes = delete_bytes

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_for_user",
            AsyncMock(return_value=[row]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_rows",
            side_effect=delete_rows,
        ),
        patch(
            "app.repositories.attachment_chunks.delete_for_attachment_ids",
            AsyncMock(),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_user(session, settings, user_id)

    assert deleted == 1
    assert order == [f"bytes:{row.storage_key}", f"rows:{row.id}"]


@pytest.mark.asyncio
async def test_purge_attachments_for_user_noop_when_empty():
    settings = Settings()
    session = AsyncMock()
    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
        ) as gateway_factory,
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_user(session, settings, uuid4())

    assert deleted == 0
    gateway_factory.assert_not_called()


@pytest.mark.asyncio
async def test_purge_attachments_for_user_continues_when_one_delete_fails():
    """One R2 failure must not abort account wipe — remaining keys + DB rows still go."""
    settings = Settings()
    user_id = uuid4()
    ok = MagicMock()
    ok.id = uuid4()
    ok.storage_key = "user/ok"
    bad = MagicMock()
    bad.id = uuid4()
    bad.storage_key = "user/bad"
    session = AsyncMock()
    deleted_keys: list[str] = []

    async def delete_bytes(key: str) -> None:
        if key == "user/bad":
            raise RuntimeError("r2 down")
        deleted_keys.append(key)

    gateway = MagicMock()
    gateway.delete_bytes = delete_bytes

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_for_user",
            AsyncMock(return_value=[ok, bad]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_rows",
            AsyncMock(return_value=2),
        ) as delete_rows,
        patch(
            "app.repositories.attachment_chunks.delete_for_attachment_ids",
            AsyncMock(),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_user(session, settings, user_id)

    assert deleted == 2
    assert deleted_keys == ["user/ok"]
    delete_rows.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_reap_orphan_attachments_refunds_image_upload_quota():
    """Reaping an uploaded image orphan must refund the daily image-upload slot —
    without this, an abandoned presign (never sent/confirmed) permanently
    consumes a slot the user can never get back."""
    settings = Settings()
    user_id = uuid4()
    orphan = MagicMock()
    orphan.id = uuid4()
    orphan.user_id = user_id
    orphan.content_type = "image/png"
    orphan.storage_key = "user/img"
    orphan.source = "upload"
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    fake_redis = AsyncMock()
    refund_upload = AsyncMock()
    refund_gen = AsyncMock()

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[orphan]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            AsyncMock(return_value=[orphan.storage_key]),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_lifecycle.get_redis_client",
            return_value=fake_redis,
        ),
        patch(
            "app.services.attachment_lifecycle.quota_service.refund_image_upload",
            refund_upload,
        ),
        patch(
            "app.services.attachment_lifecycle.quota_service.refund_image_generation",
            refund_gen,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 1
    refund_upload.assert_awaited_once_with(fake_redis, user_id)
    refund_gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_reap_orphan_attachments_refunds_image_generation_quota():
    """Reaping a generated-image orphan must refund imggen, not imgup."""
    settings = Settings()
    user_id = uuid4()
    orphan = MagicMock()
    orphan.id = uuid4()
    orphan.user_id = user_id
    orphan.content_type = "image/png"
    orphan.storage_key = "user/gen-img"
    orphan.source = "generated"
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    fake_redis = AsyncMock()
    refund_upload = AsyncMock()
    refund_gen = AsyncMock()

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[orphan]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            AsyncMock(return_value=[orphan.storage_key]),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_lifecycle.get_redis_client",
            return_value=fake_redis,
        ),
        patch(
            "app.services.attachment_lifecycle.quota_service.refund_image_upload",
            refund_upload,
        ),
        patch(
            "app.services.attachment_lifecycle.quota_service.refund_image_generation",
            refund_gen,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 1
    refund_gen.assert_awaited_once_with(fake_redis, user_id)
    refund_upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_reap_orphan_attachments_does_not_refund_for_non_image():
    """Non-image orphans (e.g. PDFs) don't consume an image slot, so no refund."""
    settings = Settings()
    user_id = uuid4()
    orphan = MagicMock()
    orphan.id = uuid4()
    orphan.user_id = user_id
    orphan.content_type = "application/pdf"
    orphan.storage_key = "user/doc"
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    fake_redis = AsyncMock()
    refund_mock = AsyncMock()

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[orphan]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            AsyncMock(return_value=[orphan.storage_key]),
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_lifecycle.get_redis_client",
            return_value=fake_redis,
        ),
        patch(
            "app.services.attachment_lifecycle.quota_service.refund_image_upload",
            refund_mock,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 1
    refund_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_reap_orphan_attachments_skips_refund_when_row_linked_after_list():
    """If a row gets linked between list and delete, it's NOT reaped and must
    NOT be refunded — the slot is still in use by the linked message."""
    settings = Settings()
    user_id = uuid4()
    orphan = MagicMock()
    orphan.id = uuid4()
    orphan.user_id = user_id
    orphan.content_type = "image/png"
    orphan.storage_key = "user/img"
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    fake_redis = AsyncMock()
    refund_mock = AsyncMock()

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[orphan]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            AsyncMock(return_value=[]),  # row was linked, nothing removed
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_lifecycle.get_redis_client",
            return_value=fake_redis,
        ),
        patch(
            "app.services.attachment_lifecycle.quota_service.refund_image_upload",
            refund_mock,
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 0
    refund_mock.assert_not_awaited()
