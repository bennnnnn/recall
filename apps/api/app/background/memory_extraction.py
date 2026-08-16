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
    existing_sections = {memory.type: memory.text for memory in existing}
    return _MemoryExtractionSnapshot(
        memory_enabled=True,
        existing_sections=existing_sections,
    )


async def extract_and_store_memories(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> str | None:
    """Run memory extraction. Returns ``\"skipped_lock\"`` when the write lock
    is busy so the job handler can re-enqueue with backoff; otherwise None.
    """
    try:
        # Holds memwrite:{user_id} for the whole read-modify-write section —
        # without it, a concurrently-running consolidation pass (or a second
        # extraction from another chat) can read the same prior section text
        # and whichever commits last silently discards the other's write.
        lock_token = await acquire_memory_write_lock(user_id)
        if not lock_token:
            logger.info("Memory extraction skipped: write lock held for user_id=%s", user_id)
            return "skipped_lock"
        try:
            async with SessionLocal() as session:
                snapshot = await _load_memory_extraction_snapshot(session, user_id)
                await session.commit()

            if not snapshot.memory_enabled:
                return None

            result = await memory_llm.revise_memory_sections(
                settings,
                transcript,
                existing_sections=snapshot.existing_sections,
            )
            if not result or not result.sections:
                return None

            rows: list[tuple[str, str, float, UUID | None]] = []
            for section in result.sections:
                prior = snapshot.existing_sections.get(section.type, "")
                accepted = accept_memory_section_rewrite(
                    section_type=section.type,
                    prior=prior,
                    summary=section.summary,
                    confidence=section.confidence,
                    min_confidence=settings.memory_min_confidence,
                )
                if accepted is None:
                    continue
                rows.append(
                    (section.type, stamp_memory_as_of(accepted), section.confidence, chat_id)
                )

            if not rows:
                return None

            await apply_memory_section_rows(
                settings,
                user_id=user_id,
                rows=rows,
                session_factory=SessionLocal,
                memories=memories_repo,
            )
        finally:
            await release_memory_write_lock(user_id, lock_token)
        return None
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
        return None
