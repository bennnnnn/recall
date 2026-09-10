"""Persist atomic memory facts, then embed without holding a DB connection."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.repositories import memories as memories_repo
from app.repositories.memory_writes import MemoryFactWrite
from app.services.memory.text import embedding_text_hash

MemorySessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def apply_memory_facts(
    settings: Settings,
    *,
    user_id: UUID,
    writes: list[MemoryFactWrite],
    session_factory: MemorySessionFactory = SessionLocal,
    memories: Any = memories_repo,
    expected_facts: dict[UUID, str] | None = None,
) -> None:
    """Persist fact ops, (re)embed stale rows, then invalidate caches."""
    if not writes:
        return

    from app.gateways import embedding_gateway

    embed_needed: list[tuple[UUID, str]] = []
    async with session_factory() as session:
        try:
            if expected_facts is not None and not await memories.lock_memory_enabled(
                session, user_id
            ):
                return
            touched = await memories.apply_writes(
                session,
                user_id=user_id,
                writes=writes,
                expected_facts=expected_facts,
                active_cap=settings.memory_active_fact_cap,
                commit=False,
            )
            updated = await memories.list_for_user(
                session, user_id, include_muted=False, include_superseded=False
            )
            touched_set = set(touched)
            backfill_left = max(0, settings.memory_embed_backfill_per_pass)
            for memory in updated:
                needs_embed = (
                    memory.embedding is None
                    or memory.embedding_json is None
                    or memory.embedding_text_hash != embedding_text_hash(memory.text)
                )
                if not needs_embed:
                    continue
                if memory.id not in touched_set:
                    if backfill_left <= 0:
                        continue
                    backfill_left -= 1
                embed_needed.append((memory.id, memory.text))
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    if not embed_needed:
        await _invalidate_memory_caches(user_id)
        return

    semaphore = asyncio.Semaphore(max(1, settings.memory_embed_concurrency))

    async def _embed(text: str) -> list[float] | None:
        async with semaphore:
            return await embedding_gateway.embed_text(settings, text)

    vectors = await asyncio.gather(*(_embed(text) for _, text in embed_needed))
    to_write: list[tuple[UUID, str, list[float], str, str]] = []
    for (memory_id, text), vec in zip(embed_needed, vectors, strict=True):
        if vec:
            to_write.append(
                (
                    memory_id,
                    text,
                    vec,
                    embedding_gateway.serialize_embedding(vec),
                    embedding_text_hash(text),
                )
            )

    if to_write:
        async with session_factory() as session:
            try:
                for memory_id, text, vec, vec_json, text_hash in to_write:
                    await memories.update_embedding_if_current(
                        session, user_id, memory_id, text, vec, vec_json, text_hash, commit=False
                    )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    await _invalidate_memory_caches(user_id)


async def apply_memory_section_rows(
    settings: Settings,
    *,
    user_id: UUID,
    rows: list[tuple[str, str, float, UUID | None]],
    session_factory: MemorySessionFactory = SessionLocal,
    memories: Any = memories_repo,
    expected_sections: dict[str, tuple[UUID, str]] | None = None,
) -> None:
    """Legacy wrapper: one add/update per type-keyed section tuple."""
    writes: list[MemoryFactWrite] = []
    expected_facts: dict[UUID, str] | None = None
    if expected_sections is not None:
        expected_facts = {memory_id: text for memory_id, text in expected_sections.values()}
    for memory_type, text, confidence, source_chat_id in rows:
        if not text.strip():
            continue
        prior = None if expected_sections is None else expected_sections.get(memory_type)
        writes.append(
            MemoryFactWrite(
                op="update" if prior is not None else "add",
                type=memory_type,
                text=text,
                confidence=confidence,
                match_text=prior[1] if prior is not None else None,
                source_chat_id=source_chat_id,
            )
        )
    await apply_memory_facts(
        settings,
        user_id=user_id,
        writes=writes,
        session_factory=session_factory,
        memories=memories,
        expected_facts=expected_facts,
    )


async def _invalidate_memory_caches(user_id: UUID) -> None:
    from app.services import home as home_service
    from app.services import memory as memory_service

    await memory_service.invalidate_memory_block(user_id)
    await home_service.invalidate_home_cache(user_id)
