"""One-turn-ahead state preload for eager WebSocket chat connections."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError
from app.models.orm import Chat, User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo
from app.services.chat.finalize_registry import get_chat_generation, wait_for_pending_finalize


@dataclass(frozen=True, slots=True)
class PreloadedChatTurnState:
    """Detached read-only state prepared while the user is reading/typing."""

    user: User
    chat: Chat
    recent_messages: list[Any]
    prior_count: int
    generation: int


async def _load_user(user_id: UUID) -> User:
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
    if user is None:
        raise ChatNotFoundError("User not found.")
    return user


async def _load_chat(chat_id: UUID, user_id: UUID) -> Chat:
    async with SessionLocal() as session:
        chat = await chats_repo.get_by_id(session, chat_id, user_id)
    if chat is None:
        raise ChatNotFoundError("Chat not found.")
    return chat


async def _load_history(chat_id: UUID, window: int) -> tuple[list[Any], int]:
    async with SessionLocal() as session:
        recent = await messages_repo.list_recent(session, chat_id, limit=window)
        if len(recent) < window:
            return recent, len(recent)
        prior_count = await messages_repo.count_for_chat(session, chat_id)
        return recent, prior_count if isinstance(prior_count, int) else len(recent)


async def preload_chat_turn_state(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
) -> PreloadedChatTurnState | None:
    """Prepare the next send during the WebSocket's idle/typing window.

    A Redis chat generation makes the snapshot single-use and cross-process
    safe: if another turn commits while these reads are in flight, retry once.
    If Redis cannot provide a generation, return None so the send path falls
    back to its normal fresh DB reads instead of trusting speculative state.
    """
    for _attempt in range(2):
        await wait_for_pending_finalize(chat_id, redis, require_complete=True)
        generation_before = await get_chat_generation(redis, chat_id)
        if generation_before is None:
            return None

        user, chat, history = await asyncio.gather(
            _load_user(user_id),
            _load_chat(chat_id, user_id),
            _load_history(chat_id, settings.recent_message_window),
        )
        recent, prior_count = history

        generation_after = await get_chat_generation(redis, chat_id)
        if generation_after is None:
            return None
        if generation_before == generation_after:
            return PreloadedChatTurnState(
                user=user,
                chat=chat,
                recent_messages=recent,
                prior_count=prior_count,
                generation=generation_after,
            )

    # The chat changed twice while we were preloading. Do not fight an active
    # conversation; the actual send path will perform fresh reads.
    return None
