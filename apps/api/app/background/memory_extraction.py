import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Memory
from app.repositories import memories as memories_repo
from app.repositories import users as users_repo
from app.services import memory_llm
from app.services.memory import (
    accept_memory_section_rewrite,
    acquire_memory_write_lock,
    embedding_text_hash,
    release_memory_write_lock,
    stamp_memory_as_of,
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
    existing_sections = {memory.type: memory.text for memory in existing}
    return _MemoryExtractionSnapshot(
        memory_enabled=True,
        existing_sections=existing_sections,
    )


async def _apply_memory_extraction_result(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    rows: list[tuple[str, str, float, UUID | None]],
) -> None:
    if not rows:
        return

    from app.gateways import embedding_gateway

    # Phase 1 — persist the text upsert and collect what needs (re)embedding,
    # then release the DB connection before the slow embedding HTTP calls.
    #
    # Re-embed any section whose embedding is missing, or whose embedding no
    # longer matches its current text.
    #
    # BUG FIX (was silent): this used to compare memory.text against the
    # existing_sections snapshot from BEFORE this call to detect "text
    # changed" — but that only catches a change within THIS call. If
    # embed_text failed right after a text change (provider hiccup), the new
    # text got written while the OLD embedding stayed in place, and nothing
    # detected that mismatch on the NEXT pass unless the text happened to
    # change again — semantic search silently misranked that memory
    # indefinitely. Comparing against the persisted embedding_text_hash
    # instead makes staleness detectable across passes, not just within one.
    embed_needed: list[tuple[UUID, str]] = []
    async with SessionLocal() as session:
        await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
        updated = await memories_repo.list_for_user(session, user_id)
        for memory in updated:
            # Re-embed if EITHER vector representation is missing — the DB
            # semantic search filters on the `embedding` (pgvector) column,
            # while the in-memory fallback reads `embedding_json`, so both
            # must be populated. Checking only `embedding_json` left rows with
            # pgvector-but-null-JSON re-embedding forever, and rows with
            # JSON-but-null-pgvector skipped entirely (invisible to DB
            # semantic search).
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
    # detects that via `embedding is None` and re-embeds — same staleness
    # recovery that already existed for a mid-pass embed failure.
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
        async with SessionLocal() as session:
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

            await _apply_memory_extraction_result(
                settings,
                user_id=user_id,
                chat_id=chat_id,
                rows=rows,
            )
        finally:
            await release_memory_write_lock(user_id, lock_token)
        return None
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
        return None
