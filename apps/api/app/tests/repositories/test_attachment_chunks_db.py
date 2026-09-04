"""Verify late attachment indexing against real ownership and cascade constraints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.config import Settings
from app.models.orm import Attachment, AttachmentChunk, Chat, Message
from app.repositories import attachment_chunks, chats, users
from app.services import attachment_lifecycle, attachment_workflow


async def _seed(session):
    user = await users.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Attachment test",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    chat_a = await chats.create(session, user_id=user.id, model="free-chat")
    chat_b = await chats.create(session, user_id=user.id, model="free-chat")
    message = Message(id=uuid4(), user_id=user.id, chat_id=chat_a.id, role="user", content="file")
    session.add(message)
    await session.flush()
    attachment = Attachment(
        id=uuid4(),
        user_id=user.id,
        message_id=message.id,
        storage_key=str(uuid4()),
        content_type="text/plain",
        size_bytes=4,
        verified_at=datetime.now(UTC),
    )
    session.add(attachment)
    await session.flush()
    session.add(
        AttachmentChunk(
            user_id=user.id,
            attachment_id=attachment.id,
            chat_id=chat_a.id,
            chunk_index=0,
            text="original index",
            embedding=[0.1] * 1536,
        )
    )
    await session.flush()
    return user, chat_a, chat_b, attachment


async def _replace(session, user, attachment, chat_id):
    return await attachment_chunks.replace_chunks(
        session,
        user_id=user.id,
        attachment_id=attachment.id,
        chat_id=chat_id,
        chunks=[(0, "replacement index", [0.2] * 1536)],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["moved_chat", "unverified", "wrong_owner"])
async def test_stale_or_unowned_index_keeps_existing_chunks(db_session, state):
    user, chat_a, chat_b, attachment = await _seed(db_session)
    target = chat_b.id if state == "moved_chat" else chat_a.id
    if state == "unverified":
        attachment.verified_at = None
        await db_session.flush()
    if state == "wrong_owner":
        user = await users.create(
            db_session,
            email=f"{uuid4()}@example.com",
            name="Other user",
            avatar_url=None,
            google_sub=str(uuid4()),
        )
    assert await _replace(db_session, user, attachment, target) is False
    assert list(
        await db_session.scalars(
            select(AttachmentChunk.text).where(AttachmentChunk.attachment_id == attachment.id)
        )
    ) == ["original index"]


@pytest.mark.asyncio
async def test_index_cannot_restore_a_deleted_file(db_session):
    user, chat_a, _, attachment = await _seed(db_session)
    await db_session.execute(delete(Attachment).where(Attachment.id == attachment.id))
    assert await _replace(db_session, user, attachment, chat_a.id) is False
    assert (
        list(
            await db_session.scalars(
                select(AttachmentChunk.id).where(AttachmentChunk.attachment_id == attachment.id)
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_library_reuse_rejects_old_job_and_indexes_current_chat(db_session):
    user, chat_a, chat_b, attachment = await _seed(db_session)
    await db_session.execute(delete(Chat).where(Chat.id == chat_a.id))
    await db_session.refresh(attachment)
    assert attachment.message_id is None
    message = Message(id=uuid4(), user_id=user.id, chat_id=chat_b.id, role="user", content="reuse")
    db_session.add(message)
    await db_session.flush()
    attachment.message_id = message.id
    await db_session.flush()

    assert await _replace(db_session, user, attachment, chat_a.id) is False
    assert await _replace(db_session, user, attachment, chat_b.id) is True
    chunks = list(
        await db_session.scalars(
            select(AttachmentChunk).where(AttachmentChunk.attachment_id == attachment.id)
        )
    )
    assert [(chunk.chat_id, chunk.text) for chunk in chunks] == [(chat_b.id, "replacement index")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["library_delete", "message_detach", "missing_file", "account_purge"]
)
async def test_attachment_service_deletion_cascades_chunks_without_touching_other_files(
    db_session, operation
):
    user, _, _, attachment = await _seed(db_session)
    _, _, _, unrelated = await _seed(db_session)
    attachment_id, unrelated_id = attachment.id, unrelated.id
    with (
        patch.object(attachment_lifecycle, "delete_storage_keys", AsyncMock(return_value=[])),
        patch.object(attachment_workflow, "delete_storage_keys", AsyncMock(return_value=[])),
        patch.object(attachment_lifecycle, "enqueue_failed_storage_deletes", AsyncMock()),
        patch.object(attachment_workflow, "enqueue_failed_storage_deletes", AsyncMock()),
    ):
        if operation == "library_delete":
            await attachment_workflow.delete_attachment(db_session, Settings(), user, attachment_id)
        elif operation == "message_detach":
            await attachment_lifecycle.detach_attachments_for_messages(
                db_session, [attachment.message_id]
            )
        elif operation == "missing_file":
            await attachment_workflow._drop_row_for_missing_file(db_session, attachment_id)
        else:
            await attachment_lifecycle.purge_attachments_for_user(db_session, Settings(), user.id)

    assert (
        await db_session.scalar(select(Attachment.id).where(Attachment.id == attachment_id)) is None
    )
    assert (
        list(
            await db_session.scalars(
                select(AttachmentChunk.id).where(AttachmentChunk.attachment_id == attachment_id)
            )
        )
        == []
    )
    assert (
        await db_session.scalar(select(Attachment.id).where(Attachment.id == unrelated_id))
        == unrelated_id
    )
    assert list(
        await db_session.scalars(
            select(AttachmentChunk.text).where(AttachmentChunk.attachment_id == unrelated_id)
        )
    ) == ["original index"]
