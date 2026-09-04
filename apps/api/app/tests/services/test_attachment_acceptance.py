"""Unavailable attachment references must fail before saving a text-only turn."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import AttachmentValidationError, ChatBusyError
from app.gateways.storage_gateway import LocalStorageGateway, StorageUnavailableError
from app.services.attachment_quota import has_current_upload_reservation
from app.services.chat.turn_prep.attachments import _process_attachments


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [False, True])
async def test_missing_or_foreign_requested_ids_fail_before_reuse(partial):
    user = SimpleNamespace(id=uuid4())
    owned = SimpleNamespace(id=uuid4())
    ids = [owned.id, uuid4()] if partial else [uuid4()]
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    with (
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=context),
        patch(
            "app.repositories.attachments.get_by_ids",
            AsyncMock(return_value=[owned] if partial else []),
        ),
        patch("app.services.attachment_reuse.ensure_unlinked_copies", AsyncMock()) as copies,
        pytest.raises(AttachmentValidationError, match="no longer available"),
    ):
        await _process_attachments(
            user_id=user.id,
            user=user,
            content="keep this",
            attachment_ids=ids,
            settings=Settings(attachments_enabled=True),
            redis=AsyncMock(),
            on_status=None,
        )
    copies.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_presign_without_upload_cannot_be_sent(tmp_path):
    user = SimpleNamespace(id=uuid4())
    row = SimpleNamespace(
        id=uuid4(),
        message_id=None,
        verified_at=None,
        storage_key="u/pending",
        size_bytes=5,
        content_type="text/plain",
    )
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    with (
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=context),
        patch("app.repositories.attachments.get_by_ids", AsyncMock(return_value=[row])),
        patch(
            "app.gateways.storage_gateway.get_storage_gateway",
            return_value=LocalStorageGateway(tmp_path),
        ),
        patch("app.services.attachment_content.purge_invalid_upload", AsyncMock()),
        pytest.raises(AttachmentValidationError, match="Upload not found"),
    ):
        await _process_attachments(
            user_id=user.id,
            user=user,
            content="keep this",
            attachment_ids=[row.id],
            settings=Settings(attachments_enabled=True),
            redis=AsyncMock(),
            on_status=None,
        )
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_storage_outage_before_acceptance_is_safe_to_retry():
    user = SimpleNamespace(id=uuid4())
    with (
        patch(
            "app.services.chat.turn_prep.attachments._process_attachment_inputs",
            AsyncMock(side_effect=StorageUnavailableError("outage")),
        ),
        pytest.raises(ChatBusyError, match="storage is temporarily unavailable"),
    ):
        await _process_attachments(
            user_id=user.id,
            user=user,
            content="keep this",
            attachment_ids=[uuid4()],
            settings=Settings(attachments_enabled=True),
            redis=AsyncMock(),
            on_status=None,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"library_visible": False},
        {"verified_at": datetime.now(UTC)},
        {"source": "generated"},
        {"created_at": datetime.now(UTC) - timedelta(days=1)},
    ],
)
def test_reuse_completed_and_previous_day_uploads_cannot_refund_today(change):
    values = dict(
        source="upload", library_visible=True, verified_at=None, created_at=datetime.now(UTC)
    )
    assert has_current_upload_reservation(SimpleNamespace(**values))
    values.update(change)
    assert not has_current_upload_reservation(SimpleNamespace(**values))
