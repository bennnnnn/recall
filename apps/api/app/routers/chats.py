from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_redis, get_settings_dep
from app.core.dev_guards import require_dev_privilege_access
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
from app.services import chats as chats_service

router = APIRouter(prefix="/chats", tags=["chats"])


def _map_error(exc: chats_service.ChatsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: ChatCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    try:
        chat = await chats_service.create_chat(
            session,
            user,
            model=body.model,
            project_id=body.project_id,
            quiz_mode=body.quiz_mode,
        )
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc
    return ChatOut.model_validate(chat)


@router.get("", response_model=ChatListOut)
async def list_chats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = chats_service.DEFAULT_CHAT_LIST_LIMIT,
) -> ChatListOut:
    return await chats_service.list_chats_grouped(session, user, limit=limit)


@router.patch("/{chat_id}", response_model=ChatOut)
async def rename_chat(
    chat_id: UUID,
    body: ChatRename,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    try:
        chat = await chats_service.rename_chat(session, user, chat_id, body.title)
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc
    return ChatOut.model_validate(chat)


@router.patch("/{chat_id}/pin", response_model=ChatOut)
async def pin_chat(
    chat_id: UUID,
    body: PinUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    try:
        chat = await chats_service.pin_chat(session, user, chat_id, pinned=body.pinned)
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc
    return ChatOut.model_validate(chat)


@router.patch("/{chat_id}/archive", response_model=ChatOut)
async def archive_chat(
    chat_id: UUID,
    body: ArchiveUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    try:
        chat = await chats_service.archive_chat(session, user, chat_id, archived=body.archived)
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc
    return ChatOut.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await chats_service.delete_chat(session, user, chat_id)
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc


@router.get("/usage/today", response_model=UsageOut)
async def today_usage(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> UsageOut:
    return await chats_service.today_usage(session, redis, settings, user)


@router.post("/usage/today/reset", response_model=UsageOut)
async def reset_today_usage(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> UsageOut:
    require_dev_privilege_access(request, settings, user)
    try:
        return await chats_service.reset_today_usage(session, redis, settings, user)
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    chat_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    try:
        chat = await chats_service.get_chat(session, user, chat_id)
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc
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
    try:
        return await chats_service.list_messages_page(
            session, redis, user, chat_id, limit=limit, before=before
        )
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc


@router.patch("/{chat_id}/messages/{message_id}/feedback", response_model=MessageOut)
async def set_message_feedback(
    chat_id: UUID,
    message_id: UUID,
    body: FeedbackUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageOut:
    try:
        message = await chats_service.set_message_feedback(
            session, user, chat_id, message_id, body.feedback
        )
    except chats_service.ChatsError as exc:
        raise _map_error(exc) from exc
    return MessageOut.model_validate(message)
