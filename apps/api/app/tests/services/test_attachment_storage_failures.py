"""Attachment outages must preserve content and retain cleanup work."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.gateways.storage_gateway import (
    LocalStorageGateway,
    R2StorageGateway,
    StorageUnavailableError,
)
from app.services import (
    attachment_content,
    attachment_lifecycle,
    attachment_upload,
    attachment_workflow,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["AccessDenied", "InternalError", "NoSuchBucket"])
async def test_storage_read_failure_does_not_purge_attachment(code):
    client = MagicMock()
    client.get_object.side_effect = ClientError({"Error": {"Code": code}}, "GetObject")
    with patch("boto3.client", return_value=client):
        gateway = R2StorageGateway(Settings())
    session = AsyncMock()
    with (
        patch.object(attachment_content, "purge_invalid_upload", AsyncMock()) as purge,
        pytest.raises(StorageUnavailableError),
    ):
        await attachment_content.ensure_verified_or_purge(
            gateway, session, attachment_id=uuid4(), content_type="text/plain", storage_key="u/a"
        )
    purge.assert_not_awaited()
    client.delete_object.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_r2_delete_remains_queued_without_remove_then_reinsert_gap():
    client = MagicMock()
    client.delete_object.side_effect = [None, RuntimeError("timeout")]
    with patch("boto3.client", return_value=client):
        gateway = R2StorageGateway(Settings())
    redis = AsyncMock()
    redis.smembers.return_value = ["u/ok", "u/retry"]
    # If re-adding failed keys is attempted, that write is unavailable too.
    redis.sadd.side_effect = RuntimeError("Redis write unavailable")
    with (
        patch.object(attachment_lifecycle, "get_storage_gateway", return_value=gateway),
        patch.object(attachment_lifecycle, "get_redis_client", return_value=redis),
    ):
        assert await attachment_lifecycle.retry_pending_storage_deletes(Settings()) == 1
    redis.srem.assert_awaited_once_with(attachment_lifecycle.PENDING_STORAGE_DELETE_KEY, "u/ok")
    redis.sadd.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_upload_preserves_bytes_when_database_delete_fails():
    gateway = MagicMock(delete_bytes=AsyncMock())
    with (
        patch(
            "app.repositories.attachments.delete_rows", AsyncMock(side_effect=RuntimeError("db"))
        ),
        pytest.raises(RuntimeError, match="db"),
    ):
        await attachment_content.purge_invalid_upload(
            gateway, AsyncMock(), attachment_id=uuid4(), storage_key="u/file"
        )
    gateway.delete_bytes.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("removed", [[], ["u/file"]])
async def test_cancel_pending_uses_committed_unlinked_delete_before_storage(removed):
    user = SimpleNamespace(id=uuid4())
    row = SimpleNamespace(
        id=uuid4(), message_id=None, content_type="text/plain", storage_key="u/file"
    )
    order = []

    async def delete_rows(*args, **kwargs):
        order.append("db")
        return removed

    async def delete_bytes(key):
        order.append("storage")
        raise StorageUnavailableError("outage")

    with (
        patch.object(attachment_upload.attachments_repo, "get_by_id", AsyncMock(return_value=row)),
        patch.object(attachment_upload.attachments_repo, "delete_unlinked_returning", delete_rows),
        patch.object(
            attachment_lifecycle,
            "get_storage_gateway",
            return_value=MagicMock(delete_bytes=delete_bytes),
        ),
        patch.object(
            attachment_lifecycle, "enqueue_failed_storage_deletes", AsyncMock()
        ) as enqueue,
    ):
        if removed:
            await attachment_upload.cancel_pending_upload(
                AsyncMock(), Settings(), user=user, attachment_id=row.id
            )
            assert order == ["db", "storage"]
            enqueue.assert_awaited_once_with(["u/file"])
        else:
            with pytest.raises(attachment_upload.AttachmentUploadError) as exc:
                await attachment_upload.cancel_pending_upload(
                    AsyncMock(), Settings(), user=user, attachment_id=row.id
                )
            assert exc.value.status_code == 409
            assert order == ["db"]
            enqueue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"original", b"replaced", b""])
async def test_verified_local_file_is_immutable_with_idempotent_upload_retry(tmp_path, payload):
    gateway = LocalStorageGateway(tmp_path)
    await gateway.write_bytes("u/retained", b"original")
    user = SimpleNamespace(id=uuid4())
    row = SimpleNamespace(
        id=uuid4(),
        message_id=None,
        content_type="text/plain",
        storage_key="u/retained",
        size_bytes=8,
        verified_at=datetime.now(UTC),
    )

    async def stream():
        yield payload

    with (
        patch.object(
            attachment_workflow.attachments_repo, "get_by_id", AsyncMock(return_value=row)
        ) as get,
        patch.object(attachment_workflow, "get_storage_gateway", return_value=gateway),
        patch.object(attachment_workflow, "purge_invalid_upload", AsyncMock()) as purge,
    ):
        if payload == b"original":
            await attachment_workflow.store_local_upload(
                AsyncMock(), Settings(), user, row.id, stream()
            )
        else:
            with pytest.raises(attachment_workflow.AttachmentWorkflowError) as exc:
                await attachment_workflow.store_local_upload(
                    AsyncMock(), Settings(), user, row.id, stream()
                )
            assert exc.value.status_code == 409
    assert await gateway.read_bytes("u/retained") == b"original"
    assert get.await_args.kwargs["for_update"] is True
    purge.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_confirm_cannot_succeed_before_upload(tmp_path):
    user = SimpleNamespace(id=uuid4())
    row = SimpleNamespace(id=uuid4(), verified_at=None)
    with (
        patch.object(
            attachment_workflow.attachments_repo, "get_by_id", AsyncMock(return_value=row)
        ),
        patch.object(
            attachment_workflow, "get_storage_gateway", return_value=LocalStorageGateway(tmp_path)
        ),
        pytest.raises(attachment_workflow.AttachmentWorkflowError) as exc,
    ):
        await attachment_workflow.confirm_upload(AsyncMock(), Settings(), user, row.id)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("removed", [0, 1])
async def test_invalid_confirmation_refunds_only_the_call_that_deleted_row(removed):
    user = SimpleNamespace(id=uuid4())
    row = SimpleNamespace(
        id=uuid4(),
        storage_key="u/pending",
        size_bytes=4,
        content_type="image/png",
        source="upload",
        library_visible=True,
        verified_at=None,
        created_at=datetime.now(UTC),
    )
    gateway = MagicMock(read_bytes=AsyncMock(return_value=b"fake"), delete_bytes=AsyncMock())
    with (
        patch.object(
            attachment_workflow.attachments_repo, "get_by_id", AsyncMock(return_value=row)
        ),
        patch.object(
            attachment_workflow.attachments_repo, "delete_rows", AsyncMock(return_value=removed)
        ),
        patch.object(attachment_workflow, "get_storage_gateway", return_value=gateway),
        patch.object(attachment_workflow, "get_redis_client", return_value=AsyncMock()),
        patch.object(
            attachment_workflow.quota_service, "refund_image_upload", AsyncMock()
        ) as refund,
        pytest.raises(attachment_workflow.AttachmentWorkflowError),
    ):
        await attachment_workflow.confirm_upload(AsyncMock(), Settings(), user, row.id)
    assert refund.await_count == removed
    assert gateway.delete_bytes.await_count == removed
