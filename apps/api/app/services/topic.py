import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.models.orm import Chat
from app.repositories import chats as chats_repo
from app.services.chat_titles import normalize_chat_title

logger = logging.getLogger(__name__)


async def _apply_chat_title(
    session: AsyncSession,
    chat_id: UUID,
    title: str,
) -> None:
    chat = await session.get(Chat, chat_id)
    if chat and not chat.title:
        await chats_repo.set_title(session, chat, title)


async def generate_chat_title(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    if not user_message.strip() or not assistant_message.strip():
        return
    try:
        title = await asyncio.wait_for(
            litellm_gateway.generate_title(settings, user_message, assistant_message),
            timeout=15.0,
        )
        title = normalize_chat_title(title)
        if not title:
            return
        async with SessionLocal() as session:
            await _apply_chat_title(session, chat_id, title)
            await session.commit()
    except Exception:
        logger.exception("Topic generation failed for chat_id=%s", chat_id)
