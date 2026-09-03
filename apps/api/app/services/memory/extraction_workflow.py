"""Extract and persist memory sections from a chat transcript."""

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
    release_memory_write_lock,
    stamp_memory_as_of,
)
from app.services.memory.apply import apply_memory_section_rows
from app.services.memory.extract_backlog import (
    expand_memory_extract_transcript,
    stamp_extract_cursor,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MemoryExtractionSnapshot:
    memory_enabled: bool
    existing_sections: dict[str, str]


async def _load_memory_extraction_snapshot(
    session: AsyncSession,
    user_id: UUID,
) -> _MemoryExtractionSnapshot:
    user = await users_repo.get_by_id(session, user_id)
    if user is None or not getattr(user, "memory_enabled", True):
        return _MemoryExtractionSnapshot(memory_enabled=False, existing_sections={})
    existing = await memories_repo.list_for_user(session, user_id)
    return _MemoryExtractionSnapshot(
        memory_enabled=True,
        existing_sections={memory.type: memory.text for memory in existing},
    )


async def extract_and_store_memories(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> str | None:
    """Return ``skipped_lock`` when a caller should retry after backoff."""
    try:
        lock_token = await acquire_memory_write_lock(user_id)
        if not lock_token:
            logger.info(
                "Memory extraction skipped: write lock held for user_id=%s",
                user_id,
            )
            return "skipped_lock"
        try:
            async with SessionLocal() as session:
                snapshot = await _load_memory_extraction_snapshot(session, user_id)
                if not snapshot.memory_enabled:
                    return None
                expanded, newest_cursor = await expand_memory_extract_transcript(
                    session,
                    user_id=user_id,
                    chat_id=chat_id,
                    fallback_transcript=transcript,
                )
            if not expanded.strip():
                return None

            result = await memory_llm.revise_memory_sections(
                settings,
                expanded,
                existing_sections=snapshot.existing_sections,
            )
            if not result or not result.sections:
                if newest_cursor:
                    await stamp_extract_cursor(user_id, chat_id, newest_cursor)
                return None

            rows: list[tuple[str, str, float, UUID | None]] = []
            for section in result.sections:
                accepted = accept_memory_section_rewrite(
                    section_type=section.type,
                    prior=snapshot.existing_sections.get(section.type, ""),
                    summary=section.summary,
                    confidence=section.confidence,
                    min_confidence=settings.memory_min_confidence,
                )
                if accepted is not None:
                    rows.append(
                        (
                            section.type,
                            stamp_memory_as_of(accepted),
                            section.confidence,
                            chat_id,
                        )
                    )
            if rows:
                await apply_memory_section_rows(
                    settings,
                    user_id=user_id,
                    rows=rows,
                    session_factory=SessionLocal,
                    memories=memories_repo,
                )
            if newest_cursor:
                await stamp_extract_cursor(user_id, chat_id, newest_cursor)
        finally:
            await release_memory_write_lock(user_id, lock_token)
        return None
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
        raise
