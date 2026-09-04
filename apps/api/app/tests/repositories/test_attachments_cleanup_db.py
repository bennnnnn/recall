"""Cleanup predicates must protect rows that changed after the reaper's snapshot."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.orm import Attachment
from app.repositories import attachments, users


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verified,visible,removed", [(False, True, True), (True, True, False), (True, False, True)]
)
async def test_reaper_rechecks_current_library_state(db_session, verified, visible, removed):
    user = await users.create(
        db_session,
        email=f"{uuid4()}@example.com",
        name="Cleanup test",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    row = Attachment(
        id=uuid4(),
        user_id=user.id,
        storage_key=f"{user.id}/{uuid4()}",
        content_type="text/plain",
        size_bytes=4,
        verified_at=datetime.now(UTC) if verified else None,
        library_visible=visible,
    )
    db_session.add(row)
    await db_session.flush()
    result = await attachments.delete_unlinked_returning(db_session, [row.id], orphan_only=True)
    assert result == ([row.storage_key] if removed else [])
    assert (
        await db_session.scalar(select(Attachment.id).where(Attachment.id == row.id)) is None
    ) is removed
