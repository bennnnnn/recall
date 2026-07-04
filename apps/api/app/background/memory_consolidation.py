import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.repositories import memories as memories_repo
from app.services.memory import (
    invalidate_memory_block,
    normalize_memory_text,
    sections_need_consolidation,
)

logger = logging.getLogger(__name__)


async def consolidate_user_memory_sections(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
) -> bool:
    """Rewrite messy section text into concise paragraphs via the memory model."""
    try:
        existing = await memories_repo.list_for_user(session, user_id)
        if not existing:
            return False

        sections = {memory.type: memory.text for memory in existing}
        if not sections_need_consolidation(sections):
            return False

        result = await litellm_gateway.rewrite_memory_sections(settings, sections)
        if not result or not result.sections:
            return False

        existing_types = set(sections)
        returned_types = {section.type for section in result.sections}
        omitted = existing_types - returned_types
        if omitted:
            logger.warning(
                "Skipping consolidation for user_id=%s: model omitted sections %s",
                user_id,
                sorted(omitted),
            )
            return False

        rows: list[tuple[str, str, float, UUID | None]] = []
        for section in result.sections:
            if section.confidence < settings.memory_min_confidence:
                continue
            summary = normalize_memory_text(section.summary)
            if not summary:
                continue
            prior = sections.get(section.type, "")
            if prior and len(summary) < len(prior) * 0.5:
                logger.warning(
                    "Skipping consolidation for %s: new text much shorter than existing",
                    section.type,
                )
                continue
            rows.append((section.type, summary, section.confidence, None))

        if not rows:
            return False

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
        return True
    except Exception:
        logger.exception("Memory consolidation failed for user_id=%s", user_id)
        return False
