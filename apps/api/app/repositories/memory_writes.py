"""Conditional background writes that preserve manual memory changes."""

from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Memory, User


async def lock_memory_enabled(session: AsyncSession, user_id: UUID) -> bool:
    """Serialize the short write phase with account toggle/deletion commits."""
    result = await session.execute(
        select(User.memory_enabled).where(User.id == user_id).with_for_update()
    )
    return bool(result.scalar_one_or_none())


async def write_rows_if_current(
    session: AsyncSession,
    user_id: UUID,
    rows: list[dict[str, Any]],
    expected_sections: dict[str, tuple[UUID, str]],
) -> None:
    """At most five section writes; the caller owns commit and rollback."""
    for row in rows:
        prior = expected_sections.get(row["type"])
        if prior is None:
            # A competing pass may have created this type while the model ran.
            stmt = (
                pg_insert(Memory)
                .values(row)
                .on_conflict_do_nothing(constraint="uq_memories_user_type")
            )
            await session.execute(stmt)
            continue
        memory_id, prior_text = prior
        unchanged = Memory.text == row["text"]
        await session.execute(
            update(Memory)
            .where(Memory.id == memory_id, Memory.user_id == user_id, Memory.text == prior_text)
            .values(
                text=row["text"],
                confidence=row["confidence"],
                source_chat_id=func.coalesce(row["source_chat_id"], Memory.source_chat_id),
                embedding=case((unchanged, Memory.embedding), else_=None),
                embedding_json=case((unchanged, Memory.embedding_json), else_=None),
                embedding_text_hash=case((unchanged, Memory.embedding_text_hash), else_=None),
                updated_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )


async def update_embedding_if_current(
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    text: str,
    embedding: list[float],
    embedding_json: str,
    embedding_text_hash: str,
    *,
    commit: bool = True,
) -> None:
    await session.execute(
        update(Memory)
        .where(Memory.id == memory_id, Memory.user_id == user_id, Memory.text == text)
        .values(
            embedding=embedding,
            embedding_json=embedding_json,
            embedding_text_hash=embedding_text_hash,
        )
        .execution_options(synchronize_session=False)
    )
    if commit:
        await session.commit()
