import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.models.orm import User
from app.models.schemas import (
    ArchiveUpdate,
    ChatCreate,
    ChatListOut,
    ChatOut,
    ChatRename,
    FeedbackUpdate,
    MessageOut,
    MessagePageOut,
    PinUpdate,
    UsageOut,
)
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import projects as projects_repo
from app.repositories import usage as usage_repo
from app.services import quota as quota_service
from app.services.chat_titles import sanitize_manual_chat_title
from app.services.quota import utc_today

router = APIRouter(prefix="/chats", tags=["chats"])

DEFAULT_CHAT_LIST_LIMIT = 200


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: ChatCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    # Verify the project belongs to this user before linking — without this a
    # client could set project_id to another user's project (FK integrity / a
    # form of cross-user metadata pollution). Downstream reads are user-scoped
    # so there's no data leak, but the link itself must be owned.
    if body.project_id is not None:
        project = await projects_repo.get_by_id(session, body.project_id, user.id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project not found")
    chat = await chats_repo.create(
        session,
        user_id=user.id,
        model=body.model,
        project_id=body.project_id,
        quiz_mode=body.quiz_mode,
    )
    return ChatOut.model_validate(chat)


@router.get("", response_model=ChatListOut)
async def list_chats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = DEFAULT_CHAT_LIST_LIMIT,
) -> ChatListOut:
    chats, archived = await asyncio.gather(
        chats_repo.list_for_user(session, user.id, limit=limit),
        chats_repo.list_archived_for_user(session, user.id, limit=50),
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


@router.patch("/{chat_id}", response_model=ChatOut)
async def rename_chat(
    chat_id: UUID,
    body: ChatRename,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    title = sanitize_manual_chat_title(body.title)
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid title")
    chat = await chats_repo.set_title(session, chat, title)
    return ChatOut.model_validate(chat)


@router.patch("/{chat_id}/pin", response_model=ChatOut)
async def pin_chat(
    chat_id: UUID,
    body: PinUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    chat = await chats_repo.set_pinned(session, chat, body.pinned)
    return ChatOut.model_validate(chat)


@router.patch("/{chat_id}/archive", response_model=ChatOut)
async def archive_chat(
    chat_id: UUID,
    body: ArchiveUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    chat = await chats_repo.set_archived(session, chat, body.archived)
    return ChatOut.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await chats_repo.delete_by_id(session, chat_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")


@router.get("/usage/today", response_model=UsageOut)
async def today_usage(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> UsageOut:
    day = utc_today()
    db_usage = await usage_repo.get_for_date(session, user.id, day)
    input_tokens = db_usage.input_tokens if db_usage else 0
    output_tokens = db_usage.output_tokens if db_usage else 0
    limit = quota_service.daily_limit_for_user(user, settings)
    redis_used = await quota_service.get_daily_usage(redis, str(user.id))
    # If Redis was flushed/evicted, fall back to the DB-recorded total so the
    # usage display never under-reports real consumption between turns.
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


@router.post("/usage/today/reset", response_model=UsageOut)
async def reset_today_usage(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> UsageOut:
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await quota_service.reset_daily_usage(redis, str(user.id))
    return await today_usage(user, session, redis, settings)


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    chat_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return ChatOut.model_validate(chat)


@router.get("/{chat_id}/messages", response_model=MessagePageOut)
async def list_messages(
    chat_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    limit: int = 40,
    before: UUID | None = None,
) -> MessagePageOut:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    msgs, has_more = await messages_repo.list_page(session, chat_id, limit=limit, before_id=before)

    # Backfill a missing title via the durable job queue. Idempotent: the handler
    # only sets a title when the chat still has none.
    if not chat.title and not before and msgs:
        user_msg = next((m for m in msgs if m.role == "user"), None)
        asst_msg = next((m for m in msgs if m.role == "assistant"), None)
        if user_msg and asst_msg:
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


@router.patch("/{chat_id}/messages/{message_id}/feedback", response_model=MessageOut)
async def set_message_feedback(
    chat_id: UUID,
    message_id: UUID,
    body: FeedbackUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    message = await messages_repo.set_feedback(session, message_id, chat_id, body.feedback)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return MessageOut.model_validate(message)
