"""Consolidate duplicate facts in persisted memory sections."""

import asyncio
import logging
from dataclasses import dataclass
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
    join_memory_facts,
    normalize_memory_text,
    release_memory_write_lock,
    section_needs_consolidation,
    sections_need_consolidation,
    split_memory_facts,
    stamp_memory_as_of,
)
from app.services.memory.apply import apply_memory_section_rows

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ConsolidationSnapshot:
    sections: dict[str, str]


async def _load_consolidation_snapshot(
    session: AsyncSession,
    user_id: UUID,
) -> _ConsolidationSnapshot | None:
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


async def _merge_one_section(
    settings: Settings,
    section_type: str,
    prior: str,
) -> tuple[str, str, float, UUID | None] | None:
    if not section_needs_consolidation(prior):
        return None
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
            return (section_type, stamp_memory_as_of(accepted), 0.95, None)
        return None

    merged = await memory_llm.merge_memory_section(
        settings,
        section_type=section_type,
        prior_text=draft,
    )
    if merged is None:
        return None
    accepted = accept_memory_section_rewrite(
        section_type=section_type,
        prior=prior,
        summary=merged.summary,
        confidence=merged.confidence,
        min_confidence=settings.memory_min_confidence,
    )
    if accepted and accepted != normalize_memory_text(prior):
        return (
            section_type,
            stamp_memory_as_of(accepted),
            merged.confidence,
            None,
        )
    return None


async def consolidate_user_memory_sections(
    settings: Settings,
    *,
    user_id: UUID,
) -> bool | str:
    """Return ``skipped_lock`` when a caller should retry after backoff."""
    try:
        lock_token = await acquire_memory_write_lock(user_id)
        if not lock_token:
            logger.info(
                "Memory consolidation skipped: write lock held for user_id=%s",
                user_id,
            )
            return "skipped_lock"
        try:
            async with SessionLocal() as session:
                snapshot = await _load_consolidation_snapshot(session, user_id)
                await session.commit()
            if snapshot is None:
                return False

            results = await asyncio.gather(
                *(
                    _merge_one_section(settings, section_type, prior)
                    for section_type, prior in snapshot.sections.items()
                ),
                return_exceptions=True,
            )
            rows: list[tuple[str, str, float, UUID | None]] = []
            for result in results:
                if isinstance(result, BaseException):
                    logger.warning(
                        "Memory consolidation section merge failed for user_id=%s",
                        user_id,
                        exc_info=result,
                    )
                elif result is not None:
                    rows.append(result)
            if not rows:
                return False

            await apply_memory_section_rows(
                settings,
                user_id=user_id,
                rows=rows,
                session_factory=SessionLocal,
                memories=memories_repo,
            )
            return True
        finally:
            await release_memory_write_lock(user_id, lock_token)
    except Exception:
        logger.exception("Memory consolidation failed for user_id=%s", user_id)
        raise
