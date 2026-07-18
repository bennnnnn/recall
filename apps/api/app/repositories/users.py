from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import (
    Attachment,
    Chat,
    Memory,
    Message,
    Project,
    ProjectItem,
    PushToken,
    SuggestedReminder,
    Suggestion,
    TodoItem,
    UsageDaily,
    User,
    UserCalendarConnection,
    UserGmailConnection,
)


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_google_sub(session: AsyncSession, google_sub: str) -> User | None:
    result = await session.execute(select(User).where(User.google_sub == google_sub))
    return result.scalar_one_or_none()


async def get_by_apple_sub(session: AsyncSession, apple_sub: str) -> User | None:
    result = await session.execute(select(User).where(User.apple_sub == apple_sub))
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    email: str,
    name: str | None,
    avatar_url: str | None,
    google_sub: str | None = None,
    apple_sub: str | None = None,
) -> User:
    if not google_sub and not apple_sub:
        raise ValueError("google_sub or apple_sub is required")
    user = User(
        google_sub=google_sub,
        apple_sub=apple_sub,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update(session: AsyncSession, user: User, **fields: Any) -> User:
    """Apply *fields* onto *user*.

    Keys present in *fields* are written as-is, including explicit ``None``
    (so nullable columns like ``custom_instructions`` / ``location`` can be
    cleared). Omit a key to leave that column unchanged.
    """
    for key, value in fields.items():
        if hasattr(user, key):
            setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: UUID) -> None:
    """Hard-delete a user and all their data.

    Deletes every user-owned row explicitly before the user row so the delete
    succeeds even for tables whose FK to users.id has no ON DELETE CASCADE
    (todos, projects, project_items, suggestions, messages, memories). Tables
    that do cascade (attachments, push tokens, connections, suggested reminders)
    are deleted explicitly too — harmless if already cascaded,
    and keeps the operation correct regardless of migration state.
    """
    await session.execute(delete(Message).where(Message.user_id == user_id))
    await session.execute(delete(Memory).where(Memory.user_id == user_id))
    await session.execute(delete(UsageDaily).where(UsageDaily.user_id == user_id))
    await session.execute(delete(ProjectItem).where(ProjectItem.user_id == user_id))
    await session.execute(delete(Project).where(Project.user_id == user_id))
    await session.execute(delete(TodoItem).where(TodoItem.user_id == user_id))
    await session.execute(delete(Suggestion).where(Suggestion.user_id == user_id))
    await session.execute(delete(SuggestedReminder).where(SuggestedReminder.user_id == user_id))
    await session.execute(delete(PushToken).where(PushToken.user_id == user_id))
    await session.execute(delete(Attachment).where(Attachment.user_id == user_id))
    await session.execute(
        delete(UserCalendarConnection).where(UserCalendarConnection.user_id == user_id)
    )
    await session.execute(delete(UserGmailConnection).where(UserGmailConnection.user_id == user_id))
    await session.execute(delete(Chat).where(Chat.user_id == user_id))
    user = await session.get(User, user_id)
    if user is not None:
        await session.delete(user)
    await session.commit()
