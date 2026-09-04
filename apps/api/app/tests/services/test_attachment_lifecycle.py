"""Attachment lifecycle service tests."""

from datetime import UTC, datetime
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
        ) as chunks,
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_messages(
            session, settings, [message_id]
        )

    assert deleted == 1
    chunks.assert_not_awaited()
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
        ) as chunks,
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_user(session, settings, user_id)

    assert deleted == 1
    chunks.assert_not_awaited()
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
            AsyncMock(return_value=1),
        ) as delete_rows,
        patch(
            "app.repositories.attachment_chunks.delete_for_attachment_ids",
            AsyncMock(),
        ) as chunks,
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_lifecycle.enqueue_failed_storage_deletes",
            AsyncMock(),
        ),
    ):
        deleted = await attachment_lifecycle.purge_attachments_for_user(session, settings, user_id)

    assert deleted == 1
    chunks.assert_not_awaited()
    assert deleted_keys == ["user/ok"]
    delete_rows.assert_awaited_once()
    assert delete_rows.await_args.args[1] == [ok.id]


@pytest.mark.asyncio
async def test_reap_orphan_attachments_skips_rows_linked_after_list():
    """DB-first: the DB unlink check (delete_unlinked_returning) runs BEFORE
    storage deletion, so a row linked between list and delete is NOT reaped
    and its bytes are NOT touched — preserving the linked attachment's
    content. Previously storage was deleted first, which could leave a linked
    attachment with missing file content."""
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
        patch(
            "app.services.attachment_lifecycle.retry_pending_storage_deletes",
            AsyncMock(return_value=0),
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 0
    delete_unlinked.assert_awaited_once()
    # DB-first: bytes are NOT deleted when the row was linked after list time.
    gateway.delete_bytes.assert_not_awaited()


@pytest.mark.asyncio
async def test_reap_orphan_attachments_deletes_db_rows_before_bytes():
    """DB-first: the reaper deletes DB rows (via delete_unlinked_returning)
    BEFORE storage bytes, so a row linked between list and delete time is
    preserved. Storage deletion only runs for rows confirmed still unlinked."""
    settings = Settings()
    orphan = MagicMock()
    orphan.id = uuid4()
    orphan.storage_key = "user/file"
    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    call_order: list[str] = []

    async def _delete_bytes(key):
        call_order.append("bytes")

    async def _delete_unlinked(session, ids, *, orphan_only):
        assert orphan_only
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
        patch(
            "app.services.attachment_lifecycle.retry_pending_storage_deletes",
            AsyncMock(return_value=0),
        ),
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    assert deleted == 1
    assert call_order == ["db", "bytes"]


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
        patch(
            "app.services.attachment_lifecycle.retry_pending_storage_deletes",
            AsyncMock(return_value=0),
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
    orphan.library_visible = True
    orphan.verified_at = None
    orphan.created_at = datetime.now(UTC)
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
async def test_reap_orphan_attachments_does_not_refund_generated_reuse_clones():
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
    refund_gen.assert_not_awaited()
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


@pytest.mark.asyncio
async def test_reap_orphan_attachments_continues_when_storage_delete_fails():
    """DB-first: a failed storage delete (for a row already removed from DB)
    is logged and skipped — it does not abort the batch. The DB row is already
    gone; failed objects must remain queued for the next cleanup pass."""
    settings = Settings()
    ok = MagicMock()
    ok.id = uuid4()
    ok.storage_key = "user/ok"
    ok.content_type = "application/pdf"
    bad = MagicMock()
    bad.id = uuid4()
    bad.storage_key = "user/bad"
    bad.content_type = "application/pdf"

    async def delete_bytes(key: str) -> None:
        if key == "user/bad":
            raise RuntimeError("r2 down")

    gateway = MagicMock()
    gateway.delete_bytes = delete_bytes

    async def delete_unlinked(_session, ids, *, orphan_only):
        assert orphan_only
        # Both rows confirmed still unlinked at delete time.
        return ["user/ok", "user/bad"]

    with (
        patch(
            "app.services.attachment_lifecycle.attachments_repo.list_orphans",
            AsyncMock(return_value=[ok, bad]),
        ),
        patch(
            "app.services.attachment_lifecycle.attachments_repo.delete_unlinked_returning",
            side_effect=delete_unlinked,
        ),
        patch(
            "app.services.attachment_lifecycle.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_lifecycle.enqueue_failed_storage_deletes", AsyncMock()
        ) as enqueue,
    ):
        deleted = await attachment_lifecycle.reap_orphan_attachments(settings)

    # Both rows were removed from the DB; the bad storage delete is best-effort.
    assert deleted == 2
    enqueue.assert_awaited_once_with(["user/bad"])


@pytest.mark.asyncio
async def test_sweep_user_storage_deletes_user_prefix():
    user_id = uuid4()
    gateway = MagicMock()
    gateway.delete_prefix = AsyncMock(return_value=3)
    with patch(
        "app.services.attachment_lifecycle.get_storage_gateway",
        return_value=gateway,
    ):
        deleted = await attachment_lifecycle.sweep_user_storage(Settings(), user_id)
    assert deleted == 3
    gateway.delete_prefix.assert_awaited_once_with(f"{user_id}/")
