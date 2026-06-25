import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.models.orm import Chat
from app.repositories import chats as chats_repo

logger = logging.getLogger(__name__)


async def generate_chat_title(
    session: AsyncSession,
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    try:
        title = await asyncio.wait_for(
            litellm_gateway.generate_title(settings, user_message, assistant_message),
            timeout=15.0,
        )
        if not title:
            return
        chat = await session.get(Chat, chat_id)
        if chat and not chat.title:
            await chats_repo.set_title(session, chat, title)
    except Exception:
        logger.exception("Topic generation failed for chat_id=%s", chat_id)
