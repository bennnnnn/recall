import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.repositories import memories as memories_repo
from app.repositories import users as users_repo
from app.services import memory_llm
from app.services.memory import (
    accept_memory_section_rewrite,
    acquire_memory_write_lock,
    embedding_text_hash,
    invalidate_memory_block,
    join_memory_facts,
    normalize_memory_text,
    release_memory_write_lock,
    section_needs_consolidation,
    sections_need_consolidation,
    split_memory_facts,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ConsolidationSnapshot:
    sections: dict[str, str]


async def _load_consolidation_snapshot(
    session: AsyncSession,
    user_id: UUID,
) -> _ConsolidationSnapshot | None:
    # Mirror memory_extraction: skip when the user is gone or has memory off.
    user = await users_repo.get_by_id(session, user_id)
    if user is None or not getattr(user, "memory_enabled", True):
        return None

    existing = await memories_repo.list_for_user(session, user_id)
    if not existing:
        return None

    sections = {memory.type: memory.text for memory in existing}
    if not sections_need_consolidation(sections):
        return None
    return _ConsolidationSnapshot(sections=sections)


async def _apply_consolidation_result(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    rows: list[tuple[str, str, float, UUID | None]],
) -> None:
    await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
    from app.gateways import embedding_gateway

    # See migration 0057: compare against the persisted embedding_text_hash
    # rather than "was this type touched by this consolidation call" so a
    # prior embed failure is detected and retried on every later pass, not
    # just the one where the text changed.
    updated = await memories_repo.list_for_user(session, user_id)
    embed_tasks: list[tuple[Any, str]] = []
    for memory in updated:
        needs_embed = (
            memory.embedding is None
            or memory.embedding_json is None
            or memory.embedding_text_hash != embedding_text_hash(memory.text)
        )
        if needs_embed:
            embed_tasks.append((memory, memory.text))

    if embed_tasks:
        vectors = await asyncio.gather(
            *(embedding_gateway.embed_text(settings, text) for _, text in embed_tasks)
        )
        for (memory, text), vec in zip(embed_tasks, vectors, strict=True):
            if vec:
                memory.embedding = vec
                memory.embedding_json = embedding_gateway.serialize_embedding(vec)
                memory.embedding_text_hash = embedding_text_hash(text)
    await session.commit()
    await invalidate_memory_block(user_id)


async def consolidate_user_memory_sections(
    settings: Settings,
    *,
    user_id: UUID,
) -> bool:
    """Merge duplicate facts per section (merge-not-replace) via the memory model."""
    try:
        # Holds the same memwrite:{user_id} lock extraction uses for its
        # read-modify-write section — without it, a concurrently-running
        # extraction pass (or a second consolidation) can read the same prior
        # section text and whichever commits last silently discards the
        # other's write.
        lock_token = await acquire_memory_write_lock(user_id)
        if not lock_token:
            logger.info("Memory consolidation skipped: write lock held for user_id=%s", user_id)
            return False
        try:
            async with SessionLocal() as session:
                snapshot = await _load_consolidation_snapshot(session, user_id)
                await session.commit()

            if snapshot is None:
                return False

            rows: list[tuple[str, str, float, UUID | None]] = []
            for section_type, prior in snapshot.sections.items():
                if not section_needs_consolidation(prior):
                    continue

                # Deterministic pre-pass: drop exact duplicate sentences before LLM.
                deduped = join_memory_facts(split_memory_facts(prior))
                draft = deduped if deduped else prior
                if draft != normalize_memory_text(prior) and not section_needs_consolidation(draft):
                    accepted = accept_memory_section_rewrite(
                        section_type=section_type,
                        prior=prior,
                        summary=draft,
                        confidence=0.95,
                        min_confidence=settings.memory_min_confidence,
                        enforce_length_floor=False,
                    )
                    if accepted and accepted != normalize_memory_text(prior):
                        rows.append((section_type, accepted, 0.95, None))
                    continue

                merged = await memory_llm.merge_memory_section(
                    settings,
                    section_type=section_type,
                    prior_text=draft,
                )
                if merged is None:
                    continue
                accepted = accept_memory_section_rewrite(
                    section_type=section_type,
                    prior=prior,
                    summary=merged.summary,
                    confidence=merged.confidence,
                    min_confidence=settings.memory_min_confidence,
                )
                if accepted and accepted != normalize_memory_text(prior):
                    rows.append((section_type, accepted, merged.confidence, None))

            if not rows:
                return False

            async with SessionLocal() as session:
                await _apply_consolidation_result(
                    session,
                    settings,
                    user_id=user_id,
                    rows=rows,
                )
            return True
        finally:
            await release_memory_write_lock(user_id, lock_token)
    except Exception:
        logger.exception("Memory consolidation failed for user_id=%s", user_id)
        return False
