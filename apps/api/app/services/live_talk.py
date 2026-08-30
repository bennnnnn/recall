"""Persist live-talk turns as normal chat messages (after the spoken stream)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Message, User
from app.models.schemas import MessageOut
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import todos as todos_service
from app.services.speech import LIVE_TALK_ALIAS
from app.services.text_normalize import cap_text_head_tail

logger = logging.getLogger(__name__)

_LIVE_TALK_RECENT = 12
_MEMORY_TRANSCRIPT_MAX_CHARS = 4000


async def load_live_talk_history(
    session: AsyncSession,
    *,
    chat_id: UUID,
    user_id: UUID,
) -> tuple[list[tuple[str, str]], bool] | None:
    """Recent text turns for the audio model, plus whether the chat still needs a title."""
    chat = await chats_repo.get_by_id(session, chat_id, user_id)
    if chat is None:
        return None
    recent = await messages_repo.list_recent(session, chat_id, limit=_LIVE_TALK_RECENT)
    history = [(row.role, row.content) for row in recent if row.role in {"user", "assistant"}]
    untitled = not (chat.title or "").strip()
    return history, untitled


def message_out_payload(message: Message | None) -> dict[str, object] | None:
    if message is None:
        return None
    return MessageOut.model_validate(message).model_dump(mode="json")


async def persist_live_talk_turn(
    *,
    user: User,
    chat_id: UUID,
    user_text: str,
    assistant_text: str,
    untitled: bool,
    settings: Settings,
    redis: Redis,
) -> tuple[Message | None, Message | None]:
    """Write user + assistant rows. Jobs enqueue after commit (must not raise)."""
    user_content = (user_text or "").strip()
    assistant_content = (assistant_text or "").strip()
    if not user_content and not assistant_content:
        return None, None

    user_message: Message | None = None
    assistant_message: Message | None = None
    async with SessionLocal() as session:
        chat = await chats_repo.get_by_id(session, chat_id, user.id)
        if chat is None:
            logger.warning("Live talk persist skipped; chat missing chat_id=%s", chat_id)
            return None, None
        if user_content:
            user_message = await messages_repo.create(
                session,
                chat_id=chat_id,
                user_id=user.id,
                role="user",
                content=user_content,
                commit=False,
            )
        if assistant_content:
            assistant_message = await messages_repo.create(
                session,
                chat_id=chat_id,
                user_id=user.id,
                role="assistant",
                content=assistant_content,
                model=LIVE_TALK_ALIAS,
                commit=False,
            )
        chat.updated_at = datetime.now(UTC)
        await session.commit()
        if user_message is not None:
            await session.refresh(user_message)
        if assistant_message is not None:
            await session.refresh(assistant_message)

    await _enqueue_live_talk_jobs(
        redis,
        settings,
        user=user,
        chat_id=chat_id,
        user_text=user_content,
        assistant_text=assistant_content,
        assistant_message_id=assistant_message.id if assistant_message is not None else None,
        untitled=untitled,
    )
    return user_message, assistant_message


async def _enqueue_live_talk_jobs(
    redis: Redis,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    user_text: str,
    assistant_text: str,
    assistant_message_id: UUID | None,
    untitled: bool,
) -> None:
    transcript = f"User: {user_text}\nAssistant: {assistant_text}"
    specs: list[tuple[str, dict[str, str], str | None]] = []
    turn_key = str(assistant_message_id) if assistant_message_id is not None else f"live:{chat_id}"
    if untitled and (user_text or assistant_text):
        specs.append(
            (
                "topic",
                {
                    "chat_id": str(chat_id),
                    "user_id": str(user.id),
                    "user_message": user_text or assistant_text,
                    "assistant_message": assistant_text,
                },
                f"topic:{chat_id}",
            )
        )
    if user.memory_enabled and user_text:
        specs.append(
            (
                "memory",
                {
                    "user_id": str(user.id),
                    "chat_id": str(chat_id),
                    "transcript": cap_text_head_tail(transcript, _MEMORY_TRANSCRIPT_MAX_CHARS),
                    "assistant_message_id": turn_key,
                },
                f"memory:{turn_key}",
            )
        )
    if todos_service.transcript_implies_todo_sync(transcript):
        specs.append(
            (
                "todos",
                {
                    "user_id": str(user.id),
                    "chat_id": str(chat_id),
                    "transcript": transcript,
                },
                f"todosync:{chat_id}:{turn_key}",
            )
        )
    if settings.chat_history_rag_enabled and assistant_message_id is not None:
        specs.append(
            (
                "message_index",
                {
                    "user_id": str(user.id),
                    "chat_id": str(chat_id),
                    "assistant_message_id": str(assistant_message_id),
                },
                f"message_index:{assistant_message_id}",
            )
        )
    try:
        for name, payload, dedupe_key in specs:
            await jobs.enqueue(redis, name, payload, dedupe_key=dedupe_key)
    except Exception:
        logger.exception("Live talk post-turn enqueue failed chat_id=%s", chat_id)
