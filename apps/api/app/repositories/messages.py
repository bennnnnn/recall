from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Message


async def create(
    session: AsyncSession,
    *,
    chat_id: UUID,
    user_id: UUID,
    role: str,
    content: str,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> Message:
    message = Message(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        content=content,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def list_recent(
    session: AsyncSession,
    chat_id: UUID,
    *,
    limit: int,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def list_all(
    session: AsyncSession,
    chat_id: UUID,
    *,
    limit: int = 200,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_page(
    session: AsyncSession,
    chat_id: UUID,
    *,
    limit: int,
    before_id: UUID | None = None,
) -> tuple[list[Message], bool]:
    """Return a chronological slice of messages (newest page or older-than cursor)."""
    capped = max(1, min(limit, 200))
    if before_id is not None:
        ref = await session.execute(
            select(Message).where(Message.id == before_id, Message.chat_id == chat_id)
        )
        anchor = ref.scalar_one_or_none()
        if anchor is None:
            return [], False
        result = await session.execute(
            select(Message)
            .where(Message.chat_id == chat_id, Message.created_at < anchor.created_at)
            .order_by(Message.created_at.desc())
            .limit(capped + 1)
        )
    else:
        result = await session.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc())
            .limit(capped + 1)
        )

    rows = list(result.scalars().all())
    has_more = len(rows) > capped
    if has_more:
        rows = rows[:capped]
    rows.reverse()
    return rows, has_more


async def list_range(
    session: AsyncSession,
    chat_id: UUID,
    *,
    offset: int,
    limit: int,
) -> list[Message]:
    """Oldest-first slice of a chat's messages — used by history compression."""
    if limit <= 0:
        return []
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_last(session: AsyncSession, chat_id: UUID) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_last_user(session: AsyncSession, chat_id: UUID) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def recent_user_contents(
    session: AsyncSession,
    chat_id: UUID,
    *,
    limit: int = 8,
) -> list[str]:
    result = await session.execute(
        select(Message.content)
        .where(Message.chat_id == chat_id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return [str(content) for content in reversed(result.scalars().all()) if str(content).strip()]


async def get_by_id(session: AsyncSession, message_id: UUID, chat_id: UUID) -> Message | None:
    result = await session.execute(
        select(Message).where(Message.id == message_id, Message.chat_id == chat_id)
    )
    return result.scalar_one_or_none()


async def delete_messages_from(
    session: AsyncSession, chat_id: UUID, *, from_created_at: datetime
) -> int:
    from sqlalchemy import delete as sql_delete

    result = await session.execute(
        sql_delete(Message).where(
            Message.chat_id == chat_id,
            Message.created_at >= from_created_at,
        )
    )
    await session.commit()
    return result.rowcount or 0


async def delete_message(session: AsyncSession, message: Message) -> None:
    await session.delete(message)
    await session.commit()


async def count_for_chat(session: AsyncSession, chat_id: UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(Message).where(Message.chat_id == chat_id)
    )
    return result.scalar_one()


async def set_feedback(
    session: AsyncSession,
    message_id: UUID,
    chat_id: UUID,
    feedback: str | None,
) -> Message | None:
    result = await session.execute(
        select(Message).where(Message.id == message_id, Message.chat_id == chat_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None
    message.feedback = feedback
    await session.commit()
    await session.refresh(message)
    return message
