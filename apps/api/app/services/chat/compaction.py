"""Chat history compaction workflow."""

import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.models.orm import Chat
from app.repositories import messages as messages_repo
from app.services.chat.summarize import summarize_conversation
from app.services.context_window import (
    cap_summary,
    compute_history_split,
    should_run_compression,
    trim_message_for_summary,
)

logger = logging.getLogger(__name__)

_COMPRESS_LOCK_TTL_SECONDS = 120


async def compress_chat_history(
    settings: Settings,
    chat_id: UUID,
    *,
    user_id: UUID | None = None,
) -> None:
    redis = get_redis_client()
    lock_key = f"chatcompress:{chat_id}"
    token = await acquire_lock(redis, lock_key, _COMPRESS_LOCK_TTL_SECONDS)
    if token is None:
        return
    try:
        async with SessionLocal() as session:
            if user_id is not None:
                from app.repositories import chats as chats_repo

                chat = await chats_repo.get_by_id(session, chat_id, user_id)
            else:
                chat = await session.get(Chat, chat_id)
            if chat is None:
                return

            total = await messages_repo.count_for_chat(session, chat_id)
            recent_all = await messages_repo.list_recent(
                session,
                chat_id,
                limit=settings.recent_message_window,
            )
            split = compute_history_split(
                total,
                recent_all,
                settings.context_token_budget,
                settings.recent_message_window,
            )
            already = chat.summary_message_count or 0
            if not should_run_compression(
                split,
                already,
                settings.history_summary_batch,
                urgent_min_pending=settings.history_summary_urgent_pending,
            ):
                return

            pending = split.summarized_count - already
            slice_messages = await messages_repo.list_range(
                session,
                chat_id,
                offset=already,
                limit=pending,
            )
            if not slice_messages:
                return
            transcript = [
                {
                    "role": message.role,
                    "content": trim_message_for_summary(message.content),
                }
                for message in slice_messages
            ]
            new_summary = await summarize_conversation(settings, chat.summary, transcript)
            if not new_summary:
                return
            chat.summary = cap_summary(new_summary)
            chat.summary_message_count = split.summarized_count
            await session.commit()
    except Exception:
        logger.exception("History compression failed for chat_id=%s", chat_id)
        raise
    finally:
        await release_lock(redis, lock_key, token)
