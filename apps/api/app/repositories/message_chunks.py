"""Message chunk repository for chat-history RAG retrieval."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import MessageChunk

EMBEDDING_DIM = 1536


async def has_chunks_for_user(session: AsyncSession, user_id: UUID) -> bool:
    result = await session.execute(
        select(MessageChunk.id)
        .where(MessageChunk.user_id == user_id, MessageChunk.embedding.isnot(None))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def count_for_user(session: AsyncSession, user_id: UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(MessageChunk).where(MessageChunk.user_id == user_id)
    )
    return int(result.scalar_one() or 0)


async def indexed_message_ids(
    session: AsyncSession,
    user_id: UUID,
    message_ids: list[UUID],
) -> set[UUID]:
    if not message_ids:
        return set()
    result = await session.execute(
        select(MessageChunk.message_id).where(
            MessageChunk.user_id == user_id,
            MessageChunk.message_id.in_(message_ids),
        )
    )
    return {row[0] for row in result.all()}


async def replace_chunks(
    session: AsyncSession,
    *,
    user_id: UUID,
    message_id: UUID,
    chat_id: UUID,
    role: str,
    chunks: list[tuple[int, str, list[float] | None]],
) -> None:
    await session.execute(delete(MessageChunk).where(MessageChunk.message_id == message_id))
    for index, text, vec in chunks:
        session.add(
            MessageChunk(
                user_id=user_id,
                message_id=message_id,
                chat_id=chat_id,
                role=role,
                chunk_index=index,
                text=text,
                embedding_json=None if vec is None else json.dumps(vec),
                embedding=vec if vec is not None and len(vec) == EMBEDDING_DIM else None,
            )
        )
    await session.commit()


async def search_semantic(
    session: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    *,
    exclude_message_ids: set[UUID] | None = None,
    limit: int = 6,
    max_distance: float | None = None,
) -> list[MessageChunk]:
    filters = [
        MessageChunk.user_id == user_id,
        MessageChunk.embedding.isnot(None),
    ]
    if exclude_message_ids:
        filters.append(MessageChunk.message_id.notin_(exclude_message_ids))

    if len(query_embedding) != EMBEDDING_DIM:
        stmt = select(MessageChunk).where(*filters)
        stmt = stmt.limit(max(limit * 4, 20))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    if max_distance is not None:
        filters.append(MessageChunk.embedding.cosine_distance(query_embedding) <= max_distance)

    stmt = (
        select(MessageChunk)
        .where(*filters)
        .order_by(MessageChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_for_message_ids(
    session: AsyncSession,
    message_ids: list[UUID],
    *,
    commit: bool = True,
) -> int:
    if not message_ids:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(delete(MessageChunk).where(MessageChunk.message_id.in_(message_ids))),
    )
    if commit:
        await session.commit()
    return int(result.rowcount or 0)
