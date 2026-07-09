import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.repositories import memories as memories_repo
from app.services.memory import (
    consolidation_rewrite_preserves_facts,
    invalidate_memory_block,
    join_memory_facts,
    normalize_memory_text,
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
    upserted_types = {memory_type for memory_type, _, _, _ in rows}
    await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
    from app.gateways import embedding_gateway

    updated = await memories_repo.list_for_user(session, user_id)
    embed_tasks: list[tuple[Any, str]] = []
    for memory in updated:
        if memory.type in upserted_types:
            embed_tasks.append((memory, memory.text))

    if embed_tasks:
        vectors = await asyncio.gather(
            *(embedding_gateway.embed_text(settings, text) for _, text in embed_tasks)
        )
        for (memory, _), vec in zip(embed_tasks, vectors, strict=True):
            if vec:
                memory.embedding = vec
                memory.embedding_json = embedding_gateway.serialize_embedding(vec)
    await session.commit()
    await invalidate_memory_block(user_id)


def _accept_merged_summary(
    *,
    section_type: str,
    prior: str,
    summary: str,
    confidence: float,
    min_confidence: float,
    enforce_length_floor: bool = True,
) -> str | None:
    if confidence < min_confidence:
        return None
    clean = normalize_memory_text(summary)
    if not clean:
        return None
    # Exact-sentence dedupe can shrink well below 50%; only LLM merges use the floor.
    if enforce_length_floor and prior and len(clean) < len(prior) * 0.5:
        logger.warning(
            "Skipping consolidation for %s: new text much shorter than existing",
            section_type,
        )
        return None
    if prior and not consolidation_rewrite_preserves_facts(prior, clean):
        logger.warning(
            "Skipping consolidation for %s: merge dropped prior fact anchors",
            section_type,
        )
        return None
    if clean == normalize_memory_text(prior):
        return None
    return clean


async def consolidate_user_memory_sections(
    settings: Settings,
    *,
    user_id: UUID,
) -> bool:
    """Merge duplicate facts per section (merge-not-replace) via the memory model."""
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
                accepted = _accept_merged_summary(
                    section_type=section_type,
                    prior=prior,
                    summary=draft,
                    confidence=0.95,
                    min_confidence=settings.memory_min_confidence,
                    enforce_length_floor=False,
                )
                if accepted:
                    rows.append((section_type, accepted, 0.95, None))
                continue

            merged = await litellm_gateway.merge_memory_section(
                settings,
                section_type=section_type,
                prior_text=draft,
            )
            if merged is None:
                continue
            accepted = _accept_merged_summary(
                section_type=section_type,
                prior=prior,
                summary=merged.summary,
                confidence=merged.confidence,
                min_confidence=settings.memory_min_confidence,
            )
            if accepted:
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
    except Exception:
        logger.exception("Memory consolidation failed for user_id=%s", user_id)
        return False
