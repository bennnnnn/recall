"""Attachment chunk repository for RAG retrieval."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import AttachmentChunk

EMBEDDING_DIM = 1536


async def delete_for_attachment_ids(session: AsyncSession, attachment_ids: list[UUID]) -> int:
    if not attachment_ids:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(AttachmentChunk).where(AttachmentChunk.attachment_id.in_(attachment_ids))
        ),
    )
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


async def replace_chunks(
    session: AsyncSession,
    *,
    user_id: UUID,
    attachment_id: UUID,
    chat_id: UUID | None,
    chunks: list[tuple[int, str, list[float] | None]],
) -> None:
    """Replace all chunks for an attachment with newly embedded ones."""
    await session.execute(
        delete(AttachmentChunk).where(AttachmentChunk.attachment_id == attachment_id)
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
