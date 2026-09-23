"""Attachment chunk repository for RAG retrieval."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Attachment, AttachmentChunk, Chat, Message

EMBEDDING_DIM = 1536


async def delete_for_attachment_ids(
    session: AsyncSession,
    attachment_ids: list[UUID],
    *,
    commit: bool = True,
) -> int:
    if not attachment_ids:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(AttachmentChunk).where(AttachmentChunk.attachment_id.in_(attachment_ids))
        ),
    )
    if commit:
        await session.commit()
    return int(result.rowcount or 0)


async def has_chunks_for_chat(
    session: AsyncSession,
    user_id: UUID,
    chat_id: UUID,
) -> bool:
    """True if this chat has at least one chunk with a retrieval embedding."""
    result = await session.execute(
        select(AttachmentChunk.id)
        .where(
            AttachmentChunk.user_id == user_id,
            AttachmentChunk.chat_id == chat_id,
            AttachmentChunk.embedding.isnot(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def has_chunks_for_attachment(
    session: AsyncSession,
    user_id: UUID,
    attachment_id: UUID,
) -> bool:
    result = await session.execute(
        select(AttachmentChunk.id)
        .where(
            AttachmentChunk.user_id == user_id,
            AttachmentChunk.attachment_id == attachment_id,
            AttachmentChunk.embedding.isnot(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def replace_chunks(
    session: AsyncSession,
    *,
    user_id: UUID,
    attachment_id: UUID,
    chat_id: UUID | None,
    chunks: list[tuple[int, str, list[float] | None]],
) -> bool:
    """Replace chunks only while the attachment still belongs to the queued chat.

    Embedding runs outside the transaction, so deletion or Library reuse can
    change this association before the worker returns. Lock the parent chat
    before its attachment, matching the order used by cascading chat deletion.
    """
    if chat_id is not None:
        current_chat = await session.scalar(
            select(Chat.id)
            .where(Chat.id == chat_id, Chat.user_id == user_id)
            .with_for_update(read=True, key_share=True)
        )
        if current_chat is None:
            return False
    attachment = await session.scalar(
        select(Attachment)
        .where(Attachment.id == attachment_id, Attachment.user_id == user_id)
        .with_for_update()
    )
    if attachment is None or attachment.verified_at is None:
        return False
    linked_chat = None
    if attachment.message_id is not None:
        linked_chat = await session.scalar(
            select(Message.chat_id).where(
                Message.id == attachment.message_id, Message.user_id == user_id
            )
        )
    if linked_chat != chat_id:
        return False
    await session.execute(
        delete(AttachmentChunk).where(
            AttachmentChunk.attachment_id == attachment_id, AttachmentChunk.user_id == user_id
        )
    )
    for index, text, vec in chunks:
        row = AttachmentChunk(
            user_id=user_id,
            attachment_id=attachment_id,
            chat_id=chat_id,
            chunk_index=index,
            text=text,
            embedding_json=None if vec is None else json.dumps(vec),
            embedding=vec if vec is not None and len(vec) == EMBEDDING_DIM else None,
        )
        session.add(row)
    await session.commit()
    return True


async def search_semantic(
    session: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    *,
    chat_id: UUID | None = None,
    limit: int = 6,
    max_distance: float | None = None,
) -> list[AttachmentChunk]:
    filters = [
        AttachmentChunk.user_id == user_id,
        AttachmentChunk.embedding.isnot(None),
    ]
    if chat_id is not None:
        filters.append(AttachmentChunk.chat_id == chat_id)

    if len(query_embedding) != EMBEDDING_DIM:
        # Mock/dev short vectors — caller ranks via embedding_json cosine.
        stmt = select(AttachmentChunk).where(*filters)
        stmt = stmt.limit(max(limit * 4, 20))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    if max_distance is not None:
        filters.append(AttachmentChunk.embedding.cosine_distance(query_embedding) <= max_distance)

    stmt = (
        select(AttachmentChunk)
        .where(*filters)
        .order_by(AttachmentChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
