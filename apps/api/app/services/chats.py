"""HTTP-facing chat list / usage / message orchestration (not the stream loop)."""

from __future__ import annotations

import asyncio
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Chat, Message, User
from app.models.schemas import ChatListOut, ChatOut, MessageOut, MessagePageOut, UsageOut
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import projects as projects_repo
from app.repositories import usage as usage_repo
from app.services import quota as quota_service
from app.services.chat import finalize_registry
from app.services.chat_titles import sanitize_manual_chat_title
from app.services.quota import utc_today

DEFAULT_CHAT_LIST_LIMIT = 200
ARCHIVED_CHAT_LIST_LIMIT = 50


class ChatsError(Exception):
    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def create_chat(
    session: AsyncSession,
    user: User,
    *,
    model: str,
    project_id: UUID | None,
    quiz_mode: str | None,
) -> Chat:
    if project_id is not None:
        project = await projects_repo.get_by_id(session, project_id, user.id)
        if project is None:
            raise ChatsError("Project not found", status_code=400)
    return await chats_repo.create(
        session,
        user_id=user.id,
        model=model,
        project_id=project_id,
        quiz_mode=quiz_mode,
    )


async def list_chats_grouped(
    session: AsyncSession,
    user: User,
    *,
    limit: int = DEFAULT_CHAT_LIST_LIMIT,
) -> ChatListOut:
    async def _archived() -> list[Chat]:
        async with SessionLocal() as archived_session:
            return await chats_repo.list_archived_for_user(
                archived_session, user.id, limit=ARCHIVED_CHAT_LIST_LIMIT
            )

    chats, archived = await asyncio.gather(
        chats_repo.list_for_user(session, user.id, limit=limit),
        _archived(),
    )
    pinned = [c for c in chats if c.pinned]
    grouped = chats_repo.group_by_recency(
        [c for c in chats if not c.pinned],
        user_timezone=user.timezone,
    )
    return ChatListOut(
        pinned=[ChatOut.model_validate(c) for c in pinned],
        today=[ChatOut.model_validate(c) for c in grouped["today"]],
        yesterday=[ChatOut.model_validate(c) for c in grouped["yesterday"]],
        last_7_days=[ChatOut.model_validate(c) for c in grouped["last_7_days"]],
        this_month=[ChatOut.model_validate(c) for c in grouped["this_month"]],
        older=[ChatOut.model_validate(c) for c in grouped["older"]],
        archived=[ChatOut.model_validate(c) for c in archived],
    )


async def get_chat(session: AsyncSession, user: User, chat_id: UUID) -> Chat:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise ChatsError("Chat not found", status_code=404)
    return chat


async def rename_chat(session: AsyncSession, user: User, chat_id: UUID, title: str) -> Chat:
    chat = await get_chat(session, user, chat_id)
    cleaned = sanitize_manual_chat_title(title)
    if not cleaned:
        raise ChatsError("Invalid title", status_code=400)
    return await chats_repo.set_title(session, chat, cleaned)


async def pin_chat(session: AsyncSession, user: User, chat_id: UUID, *, pinned: bool) -> Chat:
    chat = await get_chat(session, user, chat_id)
    return await chats_repo.set_pinned(session, chat, pinned)


async def archive_chat(session: AsyncSession, user: User, chat_id: UUID, *, archived: bool) -> Chat:
    chat = await get_chat(session, user, chat_id)
    return await chats_repo.set_archived(session, chat, archived)


async def delete_chat(session: AsyncSession, user: User, chat_id: UUID) -> None:
    deleted = await chats_repo.delete_by_id(session, chat_id, user.id)
    if not deleted:
        raise ChatsError("Chat not found", status_code=404)


async def today_usage(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user: User,
) -> UsageOut:
    day = utc_today()
    db_usage = await usage_repo.get_for_date(session, user.id, day)
    input_tokens = db_usage.input_tokens if db_usage else 0
    output_tokens = db_usage.output_tokens if db_usage else 0
    limit = quota_service.daily_limit_for_user(user, settings)
    redis_used = await quota_service.get_daily_usage(redis, str(user.id))
    used_tokens = max(redis_used, input_tokens + output_tokens)
    remaining = max(0, limit - used_tokens)
    return UsageOut(
        date=day.isoformat(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        daily_limit=limit,
        used_tokens=used_tokens,
        remaining=remaining,
    )


async def reset_today_usage(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user: User,
) -> UsageOut:
    if not settings.dev_auth_enabled:
        raise ChatsError("Not found", status_code=404)
    await quota_service.reset_daily_usage(redis, str(user.id))
    return await today_usage(session, redis, settings, user)


async def list_messages_page(
    session: AsyncSession,
    redis: Redis,
    user: User,
    chat_id: UUID,
    *,
    limit: int = 40,
    before: UUID | None = None,
) -> MessagePageOut:
    chat = await get_chat(session, user, chat_id)
    await finalize_registry.wait_for_pending_finalize(chat_id)
    msgs, has_more = await messages_repo.list_page(session, chat_id, limit=limit, before_id=before)

    if not chat.title and not before and msgs:
        user_msg = next((m for m in msgs if m.role == "user"), None)
        asst_msg = next((m for m in msgs if m.role == "assistant"), None)
        if user_msg and asst_msg:
            dedupe_key = f"topic_backfill:{chat_id}"
            claimed = await redis.set(dedupe_key, "1", nx=True, ex=300)
            if claimed:
                await jobs.enqueue(
                    redis,
                    "topic",
                    {
                        "chat_id": str(chat_id),
                        "user_message": user_msg.content,
                        "assistant_message": asst_msg.content,
                    },
                )

    return MessagePageOut(
        messages=[MessageOut.model_validate(m) for m in msgs],
        has_more=has_more,
    )


async def set_message_feedback(
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    message_id: UUID,
    feedback: str | None,
) -> Message:
    await get_chat(session, user, chat_id)
    message = await messages_repo.set_feedback(session, message_id, chat_id, feedback)
    if message is None:
        await finalize_registry.wait_for_pending_finalize(chat_id)
        message = await messages_repo.set_feedback(session, message_id, chat_id, feedback)
    if message is None:
        raise ChatsError("Message not found", status_code=404)
    return message
