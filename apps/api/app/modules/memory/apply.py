"""Persist atomic memory facts, then embed without holding a DB connection."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.modules.memory import cache
from app.modules.memory import repository as memories_repo
from app.modules.memory.text import embedding_text_hash
from app.modules.memory.writes_repository import MemoryFactWrite

logger = logging.getLogger(__name__)

MemorySessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def apply_memory_facts(
    settings: Settings,
    *,
    user_id: UUID,
    writes: list[MemoryFactWrite],
    session_factory: MemorySessionFactory = SessionLocal,
    memories: Any = memories_repo,
    expected_facts: dict[UUID, str] | None = None,
    manual_edit: bool = False,
    applied: list[str] | None = None,
    new_wins: bool = True,
    embed_timeout_seconds: float | None = None,
) -> None:
    """Persist fact ops, (re)embed stale rows, then invalidate caches.

    ``applied`` collects the op of every write that took effect. A new fact that says an
    active one again in other words replaces it; with ``new_wins`` False (the history
    scan, whose lines are older) the active one stays and the new one goes.

    ``manual_edit`` marks writes the user asked for (a plain-words edit, a
    "forget ..."). When they change or remove saved facts, the edit is stamped
    in the same transaction so the history scan cannot bring the old facts back,
    and a removed fact's past-chat snippets go with it. A background delete or
    mute (extraction housekeeping, consolidation) keeps chat history.

    ``embed_timeout_seconds`` bounds the embedding step for a caller someone waits on: past
    it the facts keep their text and a later pass embeds them.
    """
    if not writes:
        return

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
                purge_history=manual_edit,
                **({"applied": applied} if applied is not None else {}),
            )
            if manual_edit and any(write.op != "add" for write in writes):
                await memories.note_manual_edit(session, user_id)
            touched_set = set(touched)
            backfill_left = max(0, settings.memory_embed_backfill_per_pass)
            for fact_id, text, has_vector, text_hash in await memories.list_embed_state(
                session, user_id
            ):
                if has_vector and text_hash == embedding_text_hash(text):
                    continue
                if fact_id not in touched_set:
                    if backfill_left <= 0:
                        continue
                    backfill_left -= 1
                embed_needed.append((fact_id, text))
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    if not embed_needed:
        await _invalidate_memory_caches(user_id)
        return

    vectors = await _vectors(
        settings, user_id, [text for _, text in embed_needed], timeout_seconds=embed_timeout_seconds
    )
    if vectors is None:
        await _invalidate_memory_caches(user_id)
        return
    to_write = [
        (memory_id, text, vec, embedding_text_hash(text))
        for (memory_id, text), vec in zip(embed_needed, vectors, strict=True)
        if vec
    ]

    if to_write:
        async with session_factory() as session:
            try:
                for memory_id, text, vec, text_hash in to_write:
                    await memories.update_embedding_if_current(
                        session, user_id, memory_id, text, vec, text_hash, commit=False
                    )
                await _retire_said_again(
                    settings, session, memories, user_id, to_write, touched_set, new_wins
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    await _invalidate_memory_caches(user_id)


async def _retire_said_again(
    settings: Settings,
    session: AsyncSession,
    memories: Any,
    user_id: UUID,
    written: list[tuple[UUID, str, list[float], str]],
    touched: set[UUID],
    new_wins: bool,
) -> None:
    """An older fact a new or rewritten one says again in other words leaves active memory.

    A fact whose vector a later pass backfilled (its own pass ran out of time embedding,
    ``memory_instruct_embed_seconds``) is compared then: it was skipped, having no vector
    when it was written. Which of such a pair stays is decided by age (``by_age``).

    Mock vectors are all the same, so they never stand for meaning here.
    """
    from app.gateways import mock_llm

    if mock_llm.should_mock_llm(settings):
        return
    fresh = [memory_id for memory_id, *_ in written if memory_id in touched]
    backfilled = [memory_id for memory_id, *_ in written if memory_id not in touched]
    similarity = settings.memory_near_duplicate_similarity
    if fresh:
        await memories.retire_near_duplicates(
            session, user_id, fresh, min_similarity=similarity, new_wins=new_wins
        )
    if backfilled:
        await memories.retire_near_duplicates(
            session, user_id, backfilled, min_similarity=similarity, by_age=True
        )


async def _vectors(
    settings: Settings, user_id: UUID, texts: list[str], *, timeout_seconds: float | None = None
) -> list[list[float] | None] | None:
    """The facts' vectors; None while the provider is unavailable. Their text is committed
    first, and a fact with no vector is embedded by a later pass's backfill
    (``memory_embed_backfill_per_pass``), so the pass ends without rerunning its model."""
    from app.gateways import embedding_gateway

    try:
        async with asyncio.timeout(timeout_seconds):
            return await embedding_gateway.embed_many(
                settings, texts, concurrency=settings.embedding_concurrency
            )
    except (embedding_gateway.EmbeddingUnavailableError, TimeoutError):
        logger.warning("Memory embeddings left for a later pass user_id=%s", user_id)
        return None


async def _invalidate_memory_caches(user_id: UUID) -> None:
    await cache.invalidate_memory_block(user_id)
