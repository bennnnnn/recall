"""Attachment chunk repository for RAG retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.vectors import EMBEDDING_DIM, stored_vector
from app.models.orm import Attachment, AttachmentChunk, Chat, Message
from app.repositories.vector_window import nearest_in_window

__all__ = ["EMBEDDING_DIM"]


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
    """Replace chunks only while the attachment still belongs to the queued chat; no
    commit: the caller commits once its other writes (the index coverage) are in, so the
    chunks and the coverage land together under these locks.

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
            embedding=stored_vector(vec),
        )
        session.add(row)
    await session.flush()
    return True


async def search_semantic(
    session: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    *,
    window: int,
    chat_id: UUID | None = None,
    limit: int = 6,
    max_distance: float | None = None,
) -> list[AttachmentChunk]:
    """The ``limit`` chunks nearest ``query_embedding`` among the newest ``window`` of the
    chat's (or the user's) documents, ranked exactly (``repositories.vector_window``)."""
    filters: list[ColumnElement[bool]] = [AttachmentChunk.user_id == user_id]
    if chat_id is not None:
        filters.append(AttachmentChunk.chat_id == chat_id)
    return await nearest_in_window(
        session,
        AttachmentChunk,
        query_embedding,
        filters=filters,
        window=window,
        limit=limit,
        max_distance=max_distance,
    )
