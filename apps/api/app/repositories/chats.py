from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat, Message


async def create(session: AsyncSession, *, user_id: UUID, model: str) -> Chat:
    chat = Chat(user_id=user_id, model=model)
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


async def get_by_id(session: AsyncSession, chat_id: UUID, user_id: UUID) -> Chat | None:
    result = await session.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    return result.scalar_one_or_none()


async def list_for_user(
    session: AsyncSession, user_id: UUID, limit: int | None = None
) -> list[Chat]:
    has_messages = exists().where(Message.chat_id == Chat.id)
    stmt = (
        select(Chat)
        .where(Chat.user_id == user_id)
        .where(has_messages)
        .order_by(Chat.updated_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_empty_for_user(session: AsyncSession, user_id: UUID) -> int:
    """Remove chats with zero messages (abandoned drafts). Uses a single bulk DELETE."""
    empty_ids = select(Chat.id).where(
        Chat.user_id == user_id,
        ~exists().where(Message.chat_id == Chat.id),
    )
    result = await session.execute(
        delete(Chat).where(Chat.id.in_(empty_ids))
    )
    await session.commit()
    return result.rowcount


async def touch_by_id(session: AsyncSession, chat_id: UUID) -> None:
    """Update updated_at with a direct UPDATE — avoids a separate SELECT round-trip."""
    from datetime import UTC, datetime
    from sqlalchemy import update as update_stmt

    await session.execute(
        update_stmt(Chat)
        .where(Chat.id == chat_id)
        .values(updated_at=datetime.now(UTC))
    )
    await session.commit()


def group_by_recency(chats: list[Chat]) -> dict[str, list[Chat]]:
    from datetime import UTC, datetime, timedelta

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

    await session.delete(chat)
    await session.commit()
    return True


async def touch(session: AsyncSession, chat: Chat) -> None:
    from datetime import UTC, datetime

    chat.updated_at = datetime.now(UTC)
    await session.commit()


async def set_title(session: AsyncSession, chat: Chat, title: str) -> Chat:
    chat.title = title
    await session.commit()
    await session.refresh(chat)
    return chat


async def set_pinned(session: AsyncSession, chat: Chat, pinned: bool) -> Chat:
    chat.pinned = pinned
    await session.commit()
    await session.refresh(chat)
    return chat
