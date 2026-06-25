import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal, get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.models.orm import User
from app.models.schemas import ChatCreate, ChatListOut, ChatOut, ChatRename, MessageOut, UsageOut
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import usage as usage_repo
from app.services import quota as quota_service
from app.services import topic as topic_service

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: ChatCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await chats_repo.create(session, user_id=user.id, model=body.model)
    return ChatOut.model_validate(chat)


@router.get("", response_model=ChatListOut)
async def list_chats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatListOut:
    chats = await chats_repo.list_for_user(session, user.id)
    grouped = chats_repo.group_by_recency(chats)
    return ChatListOut(
        today=[ChatOut.model_validate(c) for c in grouped["today"]],
        yesterday=[ChatOut.model_validate(c) for c in grouped["yesterday"]],
        earlier=[ChatOut.model_validate(c) for c in grouped["earlier"]],
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
    chat = await chats_repo.set_title(session, chat, body.title)
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
    from datetime import date

    day = date.today()
    db_usage = await usage_repo.get_for_date(session, user.id, day)
    input_tokens = db_usage.input_tokens if db_usage else 0
    output_tokens = db_usage.output_tokens if db_usage else 0
    remaining = await quota_service.remaining(redis, str(user.id), settings)
    return UsageOut(
        date=day.isoformat(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        daily_limit=settings.daily_token_limit,
        remaining=remaining,
    )


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


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def list_messages(
    chat_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    limit: int = 200,
) -> list[MessageOut]:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    msgs = await messages_repo.list_all(session, chat_id, limit=limit)

    # Backfill title if missing and conversation already has content
    if not chat.title and msgs:
        user_msg = next((m for m in msgs if m.role == "user"), None)
        asst_msg = next((m for m in msgs if m.role == "assistant"), None)
        if user_msg and asst_msg:
            async def _backfill(cid: UUID, u: str, a: str) -> None:
                async with SessionLocal() as bg_session:
                    await topic_service.generate_chat_title(bg_session, settings, cid, u, a)
            asyncio.create_task(_backfill(chat_id, user_msg.content, asst_msg.content))

    return [MessageOut.model_validate(m) for m in msgs]
