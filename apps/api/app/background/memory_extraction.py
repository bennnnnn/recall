import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.repositories import memories as memories_repo
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
            await memories_repo.upsert_sections(session, user_id=user_id, items=rows)
            from app.gateways import embedding_gateway

            updated = await memories_repo.list_for_user(session, user_id)
            for memory in updated:
                if memory.embedding_json:
                    continue
                vec = await embedding_gateway.embed_text(settings, memory.text)
                if vec:
                    memory.embedding_json = embedding_gateway.serialize_embedding(vec)
            await session.commit()
            await memory_service.invalidate_memory_block(user_id)
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
