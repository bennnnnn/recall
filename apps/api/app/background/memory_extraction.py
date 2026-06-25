import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.repositories import memories as memories_repo

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
        result = await litellm_gateway.extract_memories(settings, transcript)
        if not result or not result.memories:
            return
        items = [
            (item.type, item.text, item.confidence, chat_id)
            for item in result.memories
            if item.confidence >= settings.memory_min_confidence
        ]
        if not items:
            return
        await memories_repo.upsert_many(session, user_id=user_id, items=items)
    except Exception:
        logger.exception("Memory extraction failed for user_id=%s", user_id)
