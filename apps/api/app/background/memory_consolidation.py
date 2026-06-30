import logging
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

        rows: list[tuple[str, str, float, UUID | None]] = []
        for section in result.sections:
            if section.confidence < settings.memory_min_confidence:
                continue
            summary = normalize_memory_text(section.summary)
            if not summary:
                continue
            rows.append((section.type, summary, section.confidence, None))

        if not rows:
            return False

        await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
        await invalidate_memory_block(user_id)
        return True
    except Exception:
        logger.exception("Memory consolidation failed for user_id=%s", user_id)
        return False
