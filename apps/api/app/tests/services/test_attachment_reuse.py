"""Tests for Library reuse clones."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import AttachmentValidationError
from app.services.attachment_reuse import ensure_unlinked_copies


@pytest.mark.asyncio
async def test_ensure_unlinked_copies_keeps_unlinked_rows():
    session = AsyncMock()
    row = MagicMock()
    row.message_id = None

    out = await ensure_unlinked_copies(session, Settings(), [row])

    assert out == [row]
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_unlinked_copies_copies_bytes_for_linked_rows():
    session = AsyncMock()
    src = MagicMock()
    src.id = uuid4()
    src.user_id = uuid4()
    src.message_id = uuid4()
    src.storage_key = "user/orig"
    src.content_type = "image/png"
    src.size_bytes = 4
    src.source = "upload"
    src.original_filename = "pic.png"
    src.verified_at = datetime(2026, 8, 1, tzinfo=UTC)

    clone = MagicMock()
    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"data")
    gateway.write_bytes = AsyncMock()

    with (
        patch(
            "app.services.attachment_reuse.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_reuse.attachments_repo.insert_verified_clone",
            AsyncMock(return_value=clone),
        ) as insert,
    ):
        out = await ensure_unlinked_copies(session, Settings(), [src])

    assert out == [clone]
    gateway.read_bytes.assert_awaited_once_with("user/orig")
    gateway.write_bytes.assert_awaited_once()
    assert str(insert.await_args.kwargs["storage_key"]).startswith(f"{src.user_id}/")
    insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_unlinked_copies_raises_when_bytes_missing():
    session = AsyncMock()
    src = MagicMock()
    src.message_id = uuid4()
    src.storage_key = "user/gone"
    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=None)

    with (
        patch(
            "app.services.attachment_reuse.get_storage_gateway",
            return_value=gateway,
        ),
        pytest.raises(AttachmentValidationError),
    ):
        await ensure_unlinked_copies(session, Settings(), [src])


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["insert", "commit", "second_write"])
async def test_clone_failure_rolls_back_and_cleans_every_attempted_object(failure):
    session = AsyncMock()
    src = MagicMock(message_id=uuid4(), storage_key="u/original", user_id=uuid4())
    gateway = MagicMock(read_bytes=AsyncMock(return_value=b"data"), write_bytes=AsyncMock())
    insert = AsyncMock(return_value=MagicMock())
    if failure == "insert":
        insert.side_effect = RuntimeError("insert")
    elif failure == "commit":
        session.commit.side_effect = RuntimeError("commit")
    else:
        gateway.write_bytes.side_effect = [None, RuntimeError("second_write")]
    with (
        patch("app.services.attachment_reuse.get_storage_gateway", return_value=gateway),
        patch("app.services.attachment_reuse.attachments_repo.insert_verified_clone", insert),
        patch(
            "app.services.attachment_lifecycle.delete_storage_keys", AsyncMock(return_value=[])
        ) as cleanup,
        pytest.raises(RuntimeError, match=failure),
    ):
        await ensure_unlinked_copies(session, Settings(), [src, src])
    session.rollback.assert_awaited_once()
    attempted_keys = [call.args[0] for call in gateway.write_bytes.await_args_list]
    assert cleanup.await_args.args[1] == attempted_keys
    assert "u/original" not in attempted_keys
