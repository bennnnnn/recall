from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat, Memory, Message


async def create(session: AsyncSession, *, user_id: UUID, model: str) -> Chat:
    chat = Chat(user_id=user_id, model=model)
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


async def get_by_id(session: AsyncSession, chat_id: UUID, user_id: UUID) -> Chat | None:
    result = await session.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Chat]:
    result = await session.execute(
        select(Chat).where(Chat.user_id == user_id).order_by(Chat.updated_at.desc())
    )
    return list(result.scalars().all())


def group_by_recency(chats: list[Chat]) -> dict[str, list[Chat]]:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    grouped: dict[str, list[Chat]] = {"today": [], "yesterday": [], "earlier": []}
    for chat in chats:
        updated = (
            chat.updated_at.replace(tzinfo=UTC)
            if chat.updated_at.tzinfo is None
            else chat.updated_at
        )
        if updated >= today_start:
            grouped["today"].append(chat)
        elif updated >= yesterday_start:
            grouped["yesterday"].append(chat)
        else:
            grouped["earlier"].append(chat)
    return grouped


async def delete_by_id(session: AsyncSession, chat_id: UUID, user_id: UUID) -> bool:
    chat = await get_by_id(session, chat_id, user_id)
    if chat is None:
        return False

    # Nullify memory source references (nullable FK — SET NULL behaviour)
    await session.execute(
        sql_update(Memory).where(Memory.source_chat_id == chat_id).values(source_chat_id=None)
    )
    # Delete all messages (non-nullable FK — must go before chat)
    await session.execute(sql_delete(Message).where(Message.chat_id == chat_id))

    await session.delete(chat)
    await session.commit()
    return True


async def touch(session: AsyncSession, chat: Chat) -> None:
    chat.updated_at = datetime.now(UTC)
    await session.commit()


async def set_title(session: AsyncSession, chat: Chat, title: str) -> Chat:
    chat.title = title
    await session.commit()
    await session.refresh(chat)
    return chat
