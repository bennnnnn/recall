from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_ops import ACTIVE_STATUS, MUTED_STATUS, normalize_memory_text
from app.models.orm import Memory
from app.repositories.memory_writes import MemoryFactWrite as MemoryFactWrite
from app.repositories.memory_writes import apply_fact_ops as apply_fact_ops
from app.repositories.memory_writes import lock_memory_enabled as lock_memory_enabled
from app.repositories.memory_writes import (
    update_embedding_if_current as update_embedding_if_current,
)


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    include_muted: bool = True,
    include_superseded: bool = False,
) -> list[Memory]:
    statuses = [ACTIVE_STATUS]
    if include_muted:
        statuses.append(MUTED_STATUS)
    filters = [Memory.user_id == user_id]
    if not include_superseded:
        filters.append(Memory.status.in_(statuses))
    result = await session.execute(
        select(Memory).where(*filters).order_by(Memory.type.asc(), Memory.last_confirmed_at.desc())
    )
    return list(result.scalars().all())


async def has_any_embedding(session: AsyncSession, user_id: UUID) -> bool:
    """True if the user has at least one memory with a populated pgvector embedding."""
    result = await session.execute(
        select(Memory.id).where(Memory.user_id == user_id, Memory.embedding.isnot(None)).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def list_range(
    session: AsyncSession,
    user_id: UUID,
    *,
    offset: int,
    limit: int,
) -> list[Memory]:
    if limit <= 0:
        return []
    result = await session.execute(
        select(Memory)
        .where(Memory.user_id == user_id, Memory.status.in_((ACTIVE_STATUS, MUTED_STATUS)))
        .order_by(Memory.type.asc(), Memory.last_confirmed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def search_semantic(
    session: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    *,
    min_confidence: float,
    limit: int,
    max_distance: float | None = None,
) -> list[Memory]:
    filters = [
        Memory.user_id == user_id,
        Memory.status == ACTIVE_STATUS,
        Memory.embedding.isnot(None),
        or_(Memory.confidence.is_(None), Memory.confidence >= min_confidence),
    ]
    if max_distance is not None:
        filters.append(Memory.embedding.cosine_distance(query_embedding) <= max_distance)
    stmt = (
        select(Memory)
        .where(*filters)
        .order_by(Memory.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def apply_writes(
    session: AsyncSession,
    *,
    user_id: UUID,
    writes: list[MemoryFactWrite],
    expected_facts: dict[UUID, str] | None,
    active_cap: int,
    commit: bool = True,
) -> list[UUID]:
    touched = await apply_fact_ops(
        session,
        user_id,
        writes,
        expected_facts,
        active_cap=active_cap,
    )
    if commit:
        await session.commit()
    else:
        await session.flush()
    return touched


async def upsert_sections(
    session: AsyncSession,
    *,
    user_id: UUID,
    items: list[tuple[str, str, float, UUID | None]],
    commit: bool = True,
    expected_sections: dict[str, tuple[UUID, str]] | None = None,
) -> None:
    """Legacy adapter for tests: one write per (type, text) tuple."""
    if not items:
        return
    writes: list[MemoryFactWrite] = []
    expected_facts: dict[UUID, str] = {}
    for memory_type, text, confidence, source_chat_id in items:
        if not text.strip():
            continue
        prior = None if expected_sections is None else expected_sections.get(memory_type)
        writes.append(
            MemoryFactWrite(
                op="update" if prior is not None else "add",
                type=memory_type,
                text=text,
                confidence=confidence,
                match_text=prior[1] if prior is not None else text,
                source_chat_id=source_chat_id,
            )
        )
        if prior is not None:
            expected_facts[prior[0]] = prior[1]
    if not writes:
        return
    await apply_writes(
        session,
        user_id=user_id,
        writes=writes,
        expected_facts=None if expected_sections is None else expected_facts,
        active_cap=150,
        commit=commit,
    )


async def delete_by_type(
    session: AsyncSession,
    user_id: UUID,
    memory_type: str,
    *,
    commit: bool = True,
) -> int:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Memory).where(Memory.user_id == user_id, Memory.type == memory_type)
        ),
    )
    if commit:
        await session.commit()
    else:
        await session.flush()
    return int(result.rowcount or 0)


async def delete_all_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    commit: bool = True,
) -> int:
    result = cast(
        CursorResult[Any],
        await session.execute(delete(Memory).where(Memory.user_id == user_id)),
    )
    if commit:
        await session.commit()
    else:
        await session.flush()
    return int(result.rowcount or 0)


async def delete_by_id(
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    *,
    commit: bool = True,
) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        ),
    )
    if commit:
        await session.commit()
    else:
        await session.flush()
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
    *,
    commit: bool = True,
) -> Memory | None:
    memory = await get_by_id(session, user_id, memory_id)
    if memory is None:
        return None
    memory.text = normalize_memory_text(text)
    memory.embedding = None
    memory.embedding_json = None
    memory.embedding_text_hash = None
    memory.last_confirmed_at = func_now()
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(memory)
    return memory


def func_now() -> datetime:
    return datetime.now(UTC)


async def update_text_and_embedding(
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    text: str,
    embedding: list[float],
    embedding_json: str,
    *,
    embedding_text_hash: str | None = None,
    commit: bool = True,
) -> Memory | None:
    """Update text and its embedding together so semantic recall doesn't rank
    on a stale vector after a fact delete/edit."""
    memory = await get_by_id(session, user_id, memory_id)
    if memory is None:
        return None
    memory.text = normalize_memory_text(text)
    memory.embedding = embedding
    memory.embedding_json = embedding_json
    memory.last_confirmed_at = func_now()
    if embedding_text_hash is not None:
        memory.embedding_text_hash = embedding_text_hash
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(memory)
    return memory


async def update_status(
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    status: str,
    *,
    commit: bool = True,
) -> Memory | None:
    memory = await get_by_id(session, user_id, memory_id)
    if memory is None:
        return None
    if memory.status == "superseded" and status != "superseded":
        return None
    memory.status = status
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(memory)
    return memory
