import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Chat
from app.repositories import chats as chats_repo
from app.services import chat_titles
from app.services.chat_titles import normalize_chat_title

logger = logging.getLogger(__name__)


async def _apply_chat_title(
    session: AsyncSession,
    chat_id: UUID,
    user_id: UUID,
    title: str,
) -> None:
    # Scope by user_id so a job injected with a known chat_id cannot set a
    # title on another user's chat (defense-in-depth: the worker stream is
    # trusted, but the job payload is now user-scoped like memory/todos).
    chat = await chats_repo.get_by_id(session, chat_id, user_id)
    if chat and not chat.title:
        await chats_repo.set_title(session, chat, title)


async def generate_chat_title(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
    *,
    user_id: UUID | None = None,
) -> None:
    if not user_message.strip() or not assistant_message.strip():
        return
    if user_id is None:
        # Backward-compat: older in-flight job payloads may omit user_id.
        # Fall back to the unscoped lookup rather than dropping the title,
        # but log so the missing scope is visible.
        logger.warning(
            "Topic job missing user_id; falling back to unscoped chat lookup chat_id=%s",
            chat_id,
        )
    try:
        title = await asyncio.wait_for(
            chat_titles.generate_title(settings, user_message, assistant_message),
            timeout=15.0,
        )
        title = normalize_chat_title(title)
        if not title:
            return
        async with SessionLocal() as session:
            if user_id is not None:
                await _apply_chat_title(session, chat_id, user_id, title)
            else:
                chat = await session.get(Chat, chat_id)
                if chat and not chat.title:
                    await chats_repo.set_title(session, chat, title)
            await session.commit()
    except Exception:
        logger.exception("Topic generation failed for chat_id=%s", chat_id)
