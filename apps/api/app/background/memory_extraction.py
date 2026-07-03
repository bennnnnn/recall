import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.models.orm import Memory
from app.repositories import memories as memories_repo
from app.repositories import users as users_repo
from app.services.memory import normalize_memory_text

logger = logging.getLogger(__name__)


async def extract_and_store_memories(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> None:
    try:
        # Respect the user's memory toggle — extraction is a no-op when off,
        # matching injection's `memory_enabled` guard in services/memory.py.
        user = await users_repo.get_by_id(session, user_id)
        if user is not None and not getattr(user, "memory_enabled", True):
            return

        existing = await memories_repo.list_for_user(session, user_id)
        existing_sections = {memory.type: memory.text for memory in existing}

        result = await litellm_gateway.revise_memory_sections(
            settings,
            transcript,
            existing_sections=existing_sections,
        )
        if not result or not result.sections:
            return

        from app.services import memory as memory_service

        rows: list[tuple[str, str, float, UUID | None]] = []
        for section in result.sections:
            if section.confidence < settings.memory_min_confidence:
                continue
            summary = normalize_memory_text(section.summary)
            if not summary:
                continue
            rows.append((section.type, summary, section.confidence, chat_id))

        if rows:
            upserted_types = {memory_type for memory_type, _, _, _ in rows}
            await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
            from app.gateways import embedding_gateway

            # Re-embed any section whose text changed (stale-vector fix) plus any
            # section that has no embedding yet. Previously only empty embeddings
            # were (re)generated, so rewrites kept the old vector.
            updated = await memories_repo.list_for_user(session, user_id)
            embed_tasks: list[tuple[Memory, str]] = []
            for memory in updated:
                needs_embed = not memory.embedding_json
                if (
                    not needs_embed
                    and memory.type in upserted_types
                    and memory.text != existing_sections.get(memory.type)
                ):
                    needs_embed = True
                if needs_embed:
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
            await memory_service.invalidate_memory_block(user_id)
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
