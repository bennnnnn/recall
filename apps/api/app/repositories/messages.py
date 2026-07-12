from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy import delete as sql_delete
from sqlalchemy.engine import CursorResult
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
    commit: bool = True,
    message_id: UUID | None = None,
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
    if message_id is not None:
        message.id = message_id
    session.add(message)
    if commit:
        await session.commit()
        await session.refresh(message)
    else:
        await session.flush()
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
        # Tuple cursor (created_at, id): same-timestamp rows stay stable across pages.
        result = await session.execute(
            select(Message)
            .where(
                Message.chat_id == chat_id,
                or_(
                    Message.created_at < anchor.created_at,
                    and_(
                        Message.created_at == anchor.created_at,
                        Message.id < anchor.id,
                    ),
                ),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(capped + 1)
        )
    else:
        result = await session.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
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
    """Oldest-first slice of a chat's messages — used by history compression.

    BUG FIX (was silent): ordering by created_at alone is not a stable sort —
    two messages created in the same millisecond can be returned in either
    order across calls, so offset/limit pagination could skip or double-count
    a row at a page boundary. Every other message-ordering query in this repo
    (delete_messages_from, ids_from_chat_at_or_after) already tuple-orders by
    (created_at, id) for exactly this reason; this one didn't. Don't drop the
    id tiebreaker again.
    """
    if limit <= 0:
        return []
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
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


async def get_last_assistant(session: AsyncSession, chat_id: UUID) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_last_quiz_assistant(
    session: AsyncSession,
    chat_id: UUID,
    *,
    lookback: int = 12,
) -> Message | None:
    """Most recent assistant message that is still an active learning/quiz prompt.

    Prefers a gradeable ```vocab_quiz fence (for MCQ chips). Falls back to
    open-ended vocab prompts (vocab_card / sentence / define) so those turns
    still get the vocab answer grading path. After a wrong MCQ the model may
    reply hint-only; the previous fence remains the one to grade against.
    """
    from app.services.projects import looks_like_vocab_question
    from app.services.vocab_quiz import parse_vocab_quiz

    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(max(1, lookback))
    )
    open_ended: Message | None = None
    for message in result.scalars().all():
        if parse_vocab_quiz(message.content) is not None:
            return message
        if open_ended is None and looks_like_vocab_question(message.content):
            open_ended = message
    return open_ended


async def count_quiz_letter_answers_since(
    session: AsyncSession,
    chat_id: UUID,
    *,
    after: datetime,
    choices: tuple[tuple[str, str], ...] | None = None,
) -> int:
    """How many A-D (or matching choice-text) answers the user sent after the open quiz."""
    from app.services.vocab_quiz import quiz_answer_letter

    result = await session.execute(
        select(Message)
        .where(
            Message.chat_id == chat_id,
            Message.role == "user",
            Message.created_at > after,
        )
        .order_by(Message.created_at.asc())
    )
    return sum(
        1
        for message in result.scalars().all()
        if quiz_answer_letter(message.content, choices=choices)
    )


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


async def ids_from_chat_at_or_after(
    session: AsyncSession,
    chat_id: UUID,
    *,
    from_created_at: datetime,
    from_message_id: UUID,
) -> list[UUID]:
    result = await session.execute(
        select(Message.id).where(
            Message.chat_id == chat_id,
            or_(
                Message.created_at > from_created_at,
                and_(
                    Message.created_at == from_created_at,
                    Message.id >= from_message_id,
                ),
            ),
        )
    )
    return list(result.scalars().all())


async def delete_messages_from(
    session: AsyncSession,
    chat_id: UUID,
    *,
    from_created_at: datetime,
    from_message_id: UUID,
) -> int:
    # Tuple ordering (created_at, id) so messages with identical timestamps are
    # deleted in stable order and the anchor message is included.
    result = await session.execute(
        sql_delete(Message).where(
            Message.chat_id == chat_id,
            or_(
                Message.created_at > from_created_at,
                and_(
                    Message.created_at == from_created_at,
                    Message.id >= from_message_id,
                ),
            ),
        )
    )
    await session.commit()
    return cast(CursorResult[Any], result).rowcount or 0


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
