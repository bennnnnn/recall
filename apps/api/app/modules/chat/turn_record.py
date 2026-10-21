"""Saving a turn chat did not stream: a picture, a photo lookup, a voice turn.

Chat owns its message rows (code-health audit ARCH-08). A typed turn saves in
``turn_settle``. Images and live talk saved their own rows and skipped what a typed
turn does after: the chat stayed where it was in the drawer, a chat that began with a
picture got no title, and memory and chat-history search never read the turn. They
save through here now, and ``finish_turn`` sets off a typed turn's jobs.
"""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Message, User
from app.modules.chat.post_turn import SavedTurn, enqueue_saved_turn_jobs
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo

logger = logging.getLogger(__name__)


async def add_turn_message(
    session: AsyncSession,
    *,
    chat_id: UUID,
    user_id: UUID,
    role: Literal["user", "assistant"],
    content: str,
    model: str | None = None,
) -> Message:
    """One message of the turn, and the chat moved up the drawer; no commit.

    The caller commits it with its own rows: a picture's attachment, a voice turn's
    reminders.
    """
    message = await messages_repo.create(
        session,
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        content=content,
        model=model,
        commit=False,
    )
    await chats_repo.touch_by_id(session, chat_id, commit=False)
    return message


async def count_messages(session: AsyncSession, chat_id: UUID) -> int:
    """How many messages the chat holds: read before a turn, its place in the chat."""
    return await messages_repo.count_for_chat(session, chat_id)


async def finish_turn(
    redis: Redis,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    user_message: str,
    assistant: Message | None,
    prior_count: int,
    run_title: bool | None = None,
) -> None:
    """After the turn committed: its title, memory, indexing and compression jobs.

    ``run_title`` defaults to a typed turn's rule, the chat's first turn. Never raises:
    the turn is saved.
    """
    saved = SavedTurn(
        user_id=user.id,
        chat_id=chat_id,
        user=user,
        user_message=user_message,
        assistant_text=assistant.content if assistant is not None else "",
        assistant_message_id=assistant.id if assistant is not None else None,
        prior_count=prior_count,
        run_title=prior_count == 0 if run_title is None else run_title,
    )
    try:
        await enqueue_saved_turn_jobs(redis, settings, saved)
    except Exception:
        logger.exception("Post-turn jobs not queued chat_id=%s", chat_id)
