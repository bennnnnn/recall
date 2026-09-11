"""Extract and persist atomic memory facts from a chat transcript."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.repositories import memories as memories_repo
from app.repositories import users as users_repo
from app.repositories.memory_writes import MemoryFactWrite
from app.services import memory_llm
from app.services.memory import (
    acquire_memory_write_lock,
    is_explicit_forget_command,
    is_explicit_memory_command,
    is_memory_candidate,
    release_memory_write_lock,
)
from app.services.memory.apply import apply_memory_facts
from app.services.memory.extract_backlog import (
    expand_memory_extract_transcript,
    stamp_extract_cursor,
)
from app.services.memory.facts import should_skip_sensitive_persist
from app.services.memory.text import classify_memory_sensitivity, normalize_memory_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MemoryExtractionSnapshot:
    memory_enabled: bool
    include_sensitive: bool
    existing_facts: dict[UUID, str]
    prompt_facts: list[dict[str, str]]


async def _load_memory_extraction_snapshot(
    session: AsyncSession,
    user_id: UUID,
) -> _MemoryExtractionSnapshot:
    user = await users_repo.get_by_id(session, user_id)
    if user is None or not getattr(user, "memory_enabled", True):
        return _MemoryExtractionSnapshot(
            memory_enabled=False,
            include_sensitive=False,
            existing_facts={},
            prompt_facts=[],
        )
    existing = await memories_repo.list_for_user(
        session, user_id, include_muted=False, include_superseded=False
    )
    return _MemoryExtractionSnapshot(
        memory_enabled=True,
        include_sensitive=bool(getattr(user, "memory_include_sensitive", False)),
        existing_facts={memory.id: memory.text for memory in existing},
        prompt_facts=[
            {"id": str(memory.id), "type": memory.type, "text": memory.text} for memory in existing
        ],
    )


def _writes_from_ops(
    result_ops: list,
    *,
    chat_id: UUID,
    explicit_remember: bool,
    include_sensitive: bool,
    min_confidence: float,
) -> tuple[list[MemoryFactWrite], int]:
    writes: list[MemoryFactWrite] = []
    skipped = 0
    for op in result_ops:
        confidence = float(op.confidence)
        if confidence < min_confidence:
            skipped += 1
            continue
        text = normalize_memory_text(op.text or "")
        sensitivity = op.sensitivity or classify_memory_sensitivity(text)
        if should_skip_sensitive_persist(
            sensitivity=sensitivity,
            text=text or op.match_text or "",
            explicit_remember=explicit_remember,
            include_sensitive=include_sensitive,
        ) and op.op in {"add", "update", "supersede"}:
            logger.info(
                "Skipping sensitive memory persist op=%s sensitivity=%s",
                op.op,
                sensitivity,
            )
            skipped += 1
            continue
        if op.op != "delete" and not text:
            skipped += 1
            continue
        writes.append(
            MemoryFactWrite(
                op=op.op,
                type=op.type,
                text=text,
                confidence=confidence,
                sensitivity=sensitivity,
                importance=float(op.importance),
                match_text=op.match_text,
                source_chat_id=chat_id,
            )
        )
    return writes, skipped


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

            forget = is_explicit_forget_command(expanded)
            explicit_remember = is_explicit_memory_command(expanded) and not forget
            if not explicit_remember and not forget and not is_memory_candidate(expanded):
                logger.info(
                    "memory_extract_yield user_id=%s applied=0 skipped=candidate",
                    user_id,
                )
                return None

            result = await memory_llm.revise_memory_facts(
                settings,
                expanded,
                existing_facts=snapshot.prompt_facts,
            )
            if not result or not result.ops:
                if newest_cursor:
                    await stamp_extract_cursor(user_id, chat_id, newest_cursor)
                logger.info("memory_extract_yield user_id=%s applied=0 skipped=empty", user_id)
                return None

            writes, skipped = _writes_from_ops(
                result.ops,
                chat_id=chat_id,
                explicit_remember=explicit_remember,
                include_sensitive=snapshot.include_sensitive,
                min_confidence=settings.memory_min_confidence,
            )
            if writes:
                await apply_memory_facts(
                    settings,
                    user_id=user_id,
                    writes=writes,
                    session_factory=SessionLocal,
                    memories=memories_repo,
                    expected_facts=snapshot.existing_facts,
                )
            logger.info(
                "memory_extract_yield user_id=%s applied=%s skipped=%s",
                user_id,
                len(writes),
                skipped,
            )
            if newest_cursor:
                await stamp_extract_cursor(user_id, chat_id, newest_cursor)
        finally:
            await release_memory_write_lock(user_id, lock_token)
        return None
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
        raise
