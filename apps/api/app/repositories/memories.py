from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Memory


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Memory]:
    result = await session.execute(
        select(Memory).where(Memory.user_id == user_id).order_by(Memory.type.asc())
    )
    return list(result.scalars().all())


async def search_semantic(
    session: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    *,
    min_confidence: float,
    limit: int,
) -> list[Memory]:
    """DB-side cosine similarity search over the `embedding` vector column
    (HNSW index). Returns up to `limit` memories ranked by cosine distance,
    filtered by confidence. Empty result means no row has a populated vector
    yet — callers fall back to the in-memory JSON path."""
    stmt = (
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.embedding.isnot(None),
            or_(Memory.confidence.is_(None), Memory.confidence >= min_confidence),
        )
        .order_by(Memory.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_sections(
    session: AsyncSession,
    *,
    user_id: UUID,
    items: list[tuple[str, str, float, UUID | None]],
) -> None:
    """Upsert one summary paragraph per memory type (profile, preference, …)."""
    if not items:
        return

    rows = [
        {
            "user_id": user_id,
            "type": memory_type,
            "text": text.strip(),
            "confidence": confidence,
            "source_chat_id": source_chat_id,
        }
        for memory_type, text, confidence, source_chat_id in items
        if text.strip()
    ]
    if not rows:
        return

    stmt = pg_insert(Memory).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_memories_user_type",
        set_={
            "text": stmt.excluded.text,
            "confidence": stmt.excluded.confidence,
            "source_chat_id": stmt.excluded.source_chat_id,
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()


async def delete_by_type(session: AsyncSession, user_id: UUID, memory_type: str) -> int:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Memory).where(Memory.user_id == user_id, Memory.type == memory_type)
        ),
    )
    await session.commit()
    return int(result.rowcount or 0)


async def delete_by_id(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        ),
    )
    await session.commit()
    return result.rowcount > 0


async def get_by_id(session: AsyncSession, user_id: UUID, memory_id: UUID) -> Memory | None:
    result = await session.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_text(
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    text: str,
) -> Memory | None:
    memory = await get_by_id(session, user_id, memory_id)
    if memory is None:
        return None
    memory.text = text.strip()
    await session.commit()
    await session.refresh(memory)
    return memory
