"""Message chunk repository for chat-history RAG retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Memory, MessageChunk

EMBEDDING_DIM = 1536


async def has_chunks_for_user(session: AsyncSession, user_id: UUID) -> bool:
    result = await session.execute(
        select(MessageChunk.id)
        .where(MessageChunk.user_id == user_id, MessageChunk.embedding.isnot(None))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def indexed_message_ids(
    session: AsyncSession,
    user_id: UUID,
    message_ids: list[UUID],
) -> set[UUID]:
    if not message_ids:
        return set()
    # Only embedded rows count: one with no vector is never found by search.
    result = await session.execute(
        select(MessageChunk.message_id).where(
            MessageChunk.user_id == user_id,
            MessageChunk.message_id.in_(message_ids),
            MessageChunk.embedding.isnot(None),
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
    commit: bool = True,
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
                embedding=vec if vec is not None and len(vec) == EMBEDDING_DIM else None,
            )
        )
    if commit:
        await session.commit()
    else:
        await session.flush()


async def search_semantic(
    session: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    *,
    window: int,
    exclude_message_ids: set[UUID] | None = None,
    limit: int = 6,
    max_distance: float | None = None,
) -> list[MessageChunk]:
    """The ``limit`` chunks nearest ``query_embedding`` among the user's newest ``window``.

    Chunks are kept as long as their chat, but a search ranks only the newest: an exact
    distance over a bounded set, read through ``(user_id, created_at)``. A global vector
    index filters by user only after its scan, so it found nothing for most users.
    """
    if len(query_embedding) != EMBEDDING_DIM:
        return []
    filters = [MessageChunk.user_id == user_id, MessageChunk.embedding.isnot(None)]
    if exclude_message_ids:
        filters.append(MessageChunk.message_id.notin_(exclude_message_ids))
    # The LIMIT keeps the planner from flattening the window into the outer query.
    newest = (
        select(MessageChunk.id, MessageChunk.embedding)
        .where(*filters)
        .order_by(MessageChunk.created_at.desc())
        .limit(window)
        .subquery("newest")
    )
    distance = newest.c.embedding.cosine_distance(query_embedding)
    stmt = select(MessageChunk).join(newest, newest.c.id == MessageChunk.id)
    if max_distance is not None:
        stmt = stmt.where(distance <= max_distance)
    result = await session.execute(stmt.order_by(distance).limit(limit))
    return list(result.scalars().all())


async def delete_near_fact(
    session: AsyncSession,
    user_id: UUID,
    fact_id: UUID,
    *,
    max_distance: float,
) -> None:
    """Drop the user's chunks within ``max_distance`` (cosine) of a memory fact's vector.

    The fact's vector is read inside the statement, never loaded; a fact with no vector
    deletes nothing. Every chunk of the user is compared, not only the window a search
    reads: a chat deleted later must not bring an older copy back into it. No commit.
    """
    fact_vector = select(Memory.embedding).where(Memory.id == fact_id).scalar_subquery()
    await session.execute(
        delete(MessageChunk).where(
            MessageChunk.user_id == user_id,
            MessageChunk.embedding.isnot(None),
            MessageChunk.embedding.cosine_distance(fact_vector) <= max_distance,
        )
    )


async def delete_mentioning_all(
    session: AsyncSession,
    user_id: UUID,
    names: list[str],
    *,
    role: str,
) -> None:
    """Drop the user's ``role`` chunks whose text names every one of ``names``; no commit."""
    if not names:
        return
    filters = [MessageChunk.user_id == user_id, MessageChunk.role == role]
    filters.extend(MessageChunk.text.icontains(name, autoescape=True) for name in names)
    await session.execute(delete(MessageChunk).where(*filters))


async def delete_all_for_user(session: AsyncSession, user_id: UUID) -> None:
    """Drop every chunk of the user's chat-history index; no commit."""
    await session.execute(delete(MessageChunk).where(MessageChunk.user_id == user_id))
