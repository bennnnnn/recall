"""Conditional background writes that preserve manual memory changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_ops import (
    ACTIVE_STATUS,
    SUPERSEDED_STATUS,
    evict_for_cap,
    match_fact,
    normalize_memory_text,
)
from app.models.orm import Memory, User


@dataclass(frozen=True)
class MemoryFactWrite:
    op: str
    type: str
    text: str
    confidence: float
    sensitivity: str = "normal"
    importance: float = 0.5
    match_text: str | None = None
    source_chat_id: UUID | None = None
    source_message_id: UUID | None = None


async def lock_memory_enabled(session: AsyncSession, user_id: UUID) -> bool:
    """Serialize the short write phase with account toggle/deletion commits."""
    result = await session.execute(
        select(User.memory_enabled).where(User.id == user_id).with_for_update()
    )
    return bool(result.scalar_one_or_none())


def _snapshot_ok(fact: Memory, expected_facts: dict[UUID, str] | None) -> bool:
    if expected_facts is None:
        return True
    prior = expected_facts.get(fact.id)
    return prior is not None and prior == fact.text


async def apply_fact_ops(
    session: AsyncSession,
    user_id: UUID,
    writes: list[MemoryFactWrite],
    expected_facts: dict[UUID, str] | None,
    *,
    active_cap: int,
) -> list[UUID]:
    """Apply add/update/supersede/delete. Returns ids whose text changed.

    The caller owns commit and rollback. When ``expected_facts`` is set, a
    late background write is skipped if the matched row's text changed.
    """
    if not writes:
        return []
    result = await session.execute(select(Memory).where(Memory.user_id == user_id))
    facts = list(result.scalars().all())
    touched: list[UUID] = []

    for write in writes:
        op = write.op
        clean = normalize_memory_text(write.text) if write.text else ""
        if op == "add":
            if not clean:
                continue
            existing = match_fact(facts, memory_type=write.type, match_text=clean)
            if existing is not None:
                if not _snapshot_ok(existing, expected_facts):
                    continue
                _apply_update(existing, write, clean)
                touched.append(existing.id)
                continue
            row = Memory(
                user_id=user_id,
                type=write.type,
                text=clean,
                confidence=write.confidence,
                status=ACTIVE_STATUS,
                sensitivity=write.sensitivity,
                importance=write.importance,
                last_confirmed_at=datetime.now(UTC),
                source_chat_id=write.source_chat_id,
                source_message_id=write.source_message_id,
            )
            session.add(row)
            await session.flush()
            facts.append(row)
            touched.append(row.id)
            continue

        matched = match_fact(
            facts,
            memory_type=write.type,
            match_text=write.match_text or write.text,
        )
        if matched is None or not _snapshot_ok(matched, expected_facts):
            continue
        if op == "delete":
            await session.delete(matched)
            facts = [fact for fact in facts if fact.id != matched.id]
            continue
        if op == "update":
            if not clean:
                continue
            _apply_update(matched, write, clean)
            touched.append(matched.id)
            continue
        if op == "supersede":
            if not clean:
                continue
            replacement = Memory(
                user_id=user_id,
                type=write.type,
                text=clean,
                confidence=write.confidence,
                status=ACTIVE_STATUS,
                sensitivity=write.sensitivity,
                importance=write.importance,
                last_confirmed_at=datetime.now(UTC),
                source_chat_id=write.source_chat_id,
                source_message_id=write.source_message_id,
            )
            session.add(replacement)
            await session.flush()
            matched.status = SUPERSEDED_STATUS
            matched.superseded_at = datetime.now(UTC)
            matched.superseded_by_id = replacement.id
            facts.append(replacement)
            touched.append(replacement.id)

    for stale in evict_for_cap(facts, active_cap):
        stale.status = SUPERSEDED_STATUS
        stale.superseded_at = datetime.now(UTC)
    return list(dict.fromkeys(touched))


def _apply_update(fact: Memory, write: MemoryFactWrite, clean: str) -> None:
    if clean != fact.text:
        fact.embedding = None
        fact.embedding_json = None
        fact.embedding_text_hash = None
    fact.text = clean
    fact.confidence = write.confidence
    fact.sensitivity = write.sensitivity
    fact.importance = write.importance
    fact.last_confirmed_at = datetime.now(UTC)
    if write.source_chat_id is not None:
        fact.source_chat_id = write.source_chat_id
    if write.source_message_id is not None:
        fact.source_message_id = write.source_message_id
    fact.updated_at = datetime.now(UTC)


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
