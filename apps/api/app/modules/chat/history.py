"""What other modules read of a user's chats.

Chat owns the chats, messages and message chunks (code-health audit ARCH-08): their
repositories sit in this module and stay private. Images, live talk, to-dos, memory,
attachments and the account read through these operations; a turn chat did not stream
saves through ``turn_record``, and memory forgets past snippets through ``history_rag``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat, Message
from app.modules.chat import chats_repository as _chats
from app.modules.chat import messages_repository as _messages


async def get_chat(session: AsyncSession, chat_id: UUID, user_id: UUID) -> Chat | None:
    """The user's chat, or None when it is not theirs or is gone."""
    return await _chats.get_by_id(session, chat_id, user_id)


async def recent_messages(session: AsyncSession, chat_id: UUID, *, limit: int) -> list[Message]:
    """The chat's last ``limit`` messages, oldest first."""
    return await _messages.list_recent(session, chat_id, limit=limit)


async def last_user_message(session: AsyncSession, chat_id: UUID) -> Message | None:
    """The chat's latest message from the user."""
    return await _messages.get_last_user(session, chat_id)


async def message_in_chat(session: AsyncSession, message_id: UUID, chat_id: UUID) -> Message | None:
    """The message, when it belongs to this chat."""
    return await _messages.get_by_id(session, message_id, chat_id)


async def message_for_user(
    session: AsyncSession, message_id: UUID, user_id: UUID
) -> Message | None:
    """The message, when it is in one of the user's chats."""
    return await _messages.get_for_user(session, message_id, user_id)


async def user_lines_since(
    session: AsyncSession,
    chat_id: UUID,
    *,
    after_created_at: datetime | None = None,
    after_id: UUID | None = None,
    newer_than: datetime | None = None,
    limit: int = 20,
) -> list[Message]:
    """The user's messages after an extract cursor, oldest first (memory's backlog)."""
    return await _messages.list_user_contents_since(
        session,
        chat_id,
        after_created_at=after_created_at,
        after_id=after_id,
        newer_than=newer_than,
        limit=limit,
    )


async def messages_before(
    session: AsyncSession, chat_id: UUID, message: Message, *, limit: int
) -> list[Message]:
    """Up to ``limit`` messages just before ``message``, oldest first."""
    return await _messages.list_before(
        session,
        chat_id,
        before_created_at=message.created_at,
        before_id=message.id,
        limit=limit,
    )


async def chats_for_export(session: AsyncSession, user_id: UUID, *, limit: int) -> list[Chat]:
    """The user's chats, archived ones too, each with its summary (the data export)."""
    return await _chats.list_for_user(
        session, user_id, limit=limit, include_archived=True, with_summary=True
    )


async def messages_page(
    session: AsyncSession, chat_id: UUID, *, offset: int, limit: int
) -> list[Message]:
    """An oldest-first slice of the chat's messages (the export pages through them)."""
    return await _messages.list_range(session, chat_id, offset=offset, limit=limit)


def forget_user_chats(user_id: UUID) -> None:
    """Drop the user's chats this process remembers (the account is being deleted)."""
    _chats.forget_user_chats(user_id)
