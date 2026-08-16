"""Persist memory section rows, then embed without holding a DB connection."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Memory
from app.repositories import memories as memories_repo
from app.services.memory.text import embedding_text_hash

MemorySessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def apply_memory_section_rows(
    settings: Settings,
    *,
    user_id: UUID,
    rows: list[tuple[str, str, float, UUID | None]],
    session_factory: MemorySessionFactory = SessionLocal,
    memories: Any = memories_repo,
) -> None:
    """Upsert section text, (re)embed stale rows, then invalidate caches.

    ``session_factory`` / ``memories`` default to the production seams; callers
    in the background jobs pass their module-level bindings so existing tests
    that patch those names still cover this write path.
    """
    if not rows:
        return

    from app.gateways import embedding_gateway

    # Phase 1 — persist the text upsert and collect what needs (re)embedding,
    # then release the DB connection before the slow embedding HTTP calls.
    #
    # Re-embed any section whose embedding is missing, or whose embedding no
    # longer matches its current text.
    #
    # Compare against the persisted embedding_text_hash rather than "was this
    # type touched by this call" so a prior embed failure is retried on every
    # later pass, not just the one where the text changed.
    embed_needed: list[tuple[UUID, str]] = []
    async with session_factory() as session:
        await memories.upsert_sections(session, user_id=user_id, items=rows)
        updated = await memories.list_for_user(session, user_id)
        for memory in updated:
            # Re-embed if EITHER vector representation is missing — the DB
            # semantic search filters on the `embedding` (pgvector) column,
            # while the in-memory fallback reads `embedding_json`, so both
            # must be populated.
            needs_embed = (
                memory.embedding is None
                or memory.embedding_json is None
                or memory.embedding_text_hash != embedding_text_hash(memory.text)
            )
            if needs_embed:
                embed_needed.append((memory.id, memory.text))
        await session.commit()

    if not embed_needed:
        await _invalidate_memory_caches(user_id)
        return

    # Phase 2 — embed with no DB connection held (slow provider HTTP). A
    # failure here leaves the text persisted with no vector; the next pass
    # detects that via `embedding is None` and re-embeds.
    vectors = await asyncio.gather(
        *(embedding_gateway.embed_text(settings, text) for _, text in embed_needed)
    )
    to_write: list[tuple[UUID, list[float], str, str]] = []
    for (memory_id, text), vec in zip(embed_needed, vectors, strict=True):
        if vec:
            to_write.append(
                (
                    memory_id,
                    vec,
                    embedding_gateway.serialize_embedding(vec),
                    embedding_text_hash(text),
                )
            )

    # Phase 3 — write vectors in a fresh short-lived session.
    if to_write:
        async with session_factory() as session:
            for memory_id, vec, vec_json, text_hash in to_write:
                row = await session.get(Memory, memory_id)
                if row is None:
                    continue
                row.embedding = vec
                row.embedding_json = vec_json
                row.embedding_text_hash = text_hash
            await session.commit()

    await _invalidate_memory_caches(user_id)


async def _invalidate_memory_caches(user_id: UUID) -> None:
    from app.services import home as home_service
    from app.services import memory as memory_service

    await memory_service.invalidate_memory_block(user_id)
    await home_service.invalidate_home_cache(user_id)
