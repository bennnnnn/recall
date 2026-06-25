from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Memory


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Memory]:
    result = await session.execute(
        select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc())
    )
    return list(result.scalars().all())


async def upsert_many(
    session: AsyncSession,
    *,
    user_id: UUID,
    items: list[tuple[str, str, float, UUID | None]],
) -> None:
    """Single-query upsert using PostgreSQL ON CONFLICT DO UPDATE (O(1) queries)."""
    if not items:
        return

    rows = [
        {
            "user_id": user_id,
            "type": memory_type,
            "text": text,
            "confidence": confidence,
            "source_chat_id": source_chat_id,
        }
        for memory_type, text, confidence, source_chat_id in items
    ]

    stmt = pg_insert(Memory).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_memories_user_type_text",
        set_={
            "confidence": stmt.excluded.confidence,
            "source_chat_id": stmt.excluded.source_chat_id,
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()


async def delete_by_id(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    result = await session.execute(
        delete(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    )
    await session.commit()
    return result.rowcount > 0
