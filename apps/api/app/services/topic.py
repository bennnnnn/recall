import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.modules.chat import titles as chat_titles
from app.modules.chat.titles import normalize_chat_title
from app.repositories import chats as chats_repo

logger = logging.getLogger(__name__)


async def generate_chat_title(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
    *,
    user_id: UUID,
) -> bool:
    """Title the chat from its first exchange; True when a title was applied.

    False (nothing usable, or the chat already has a title) leaves the job not done,
    so a later request may try again; the caller says so to the queue.
    """
    if not user_message.strip() or not assistant_message.strip():
        return False
    try:
        title = await asyncio.wait_for(
            chat_titles.generate_title(settings, user_message, assistant_message),
            timeout=15.0,
        )
        title = normalize_chat_title(title)
        if not title:
            return False
        async with SessionLocal() as session:
            applied = await chats_repo.set_title_if_empty(
                session, chat_id, title, user_id=user_id, commit=False
            )
            await session.commit()
        return applied
    except Exception:
        logger.exception("Topic generation failed for chat_id=%s", chat_id)
        raise
