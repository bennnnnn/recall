import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.models.orm import Memory
from app.repositories import memories as memories_repo
from app.repositories import users as users_repo
from app.services.memory import embedding_text_hash, normalize_memory_text

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
    memory_enabled = user is None or getattr(user, "memory_enabled", True)
    if not memory_enabled:
        return _MemoryExtractionSnapshot(memory_enabled=False, existing_sections={})

    existing = await memories_repo.list_for_user(session, user_id)
    existing_sections = {memory.type: memory.text for memory in existing}
    return _MemoryExtractionSnapshot(
        memory_enabled=True,
        existing_sections=existing_sections,
    )


async def _apply_memory_extraction_result(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    rows: list[tuple[str, str, float, UUID | None]],
) -> None:
    if not rows:
        return

    await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
    from app.gateways import embedding_gateway

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
    updated = await memories_repo.list_for_user(session, user_id)
    embed_tasks: list[tuple[Memory, str]] = []
    for memory in updated:
        # Re-embed if EITHER vector representation is missing — the DB semantic
        # search filters on the `embedding` (pgvector) column, while the
        # in-memory fallback reads `embedding_json`, so both must be populated.
        # Checking only `embedding_json` left rows with pgvector-but-null-JSON
        # re-embedding forever, and rows with JSON-but-null-pgvector skipped
        # entirely (invisible to DB semantic search).
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
    from app.services import memory as memory_service

    await memory_service.invalidate_memory_block(user_id)
    from app.services import home as home_service

    await home_service.invalidate_home_cache(user_id)


async def extract_and_store_memories(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> None:
    try:
        async with SessionLocal() as session:
            snapshot = await _load_memory_extraction_snapshot(session, user_id)
            await session.commit()

        if not snapshot.memory_enabled:
            return

        result = await litellm_gateway.revise_memory_sections(
            settings,
            transcript,
            existing_sections=snapshot.existing_sections,
        )
        if not result or not result.sections:
            return

        rows: list[tuple[str, str, float, UUID | None]] = []
        for section in result.sections:
            if section.confidence < settings.memory_min_confidence:
                continue
            summary = normalize_memory_text(section.summary)
            if not summary:
                continue
            rows.append((section.type, summary, section.confidence, chat_id))

        if not rows:
            return

        async with SessionLocal() as session:
            await _apply_memory_extraction_result(
                session,
                settings,
                user_id=user_id,
                chat_id=chat_id,
                rows=rows,
            )
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
