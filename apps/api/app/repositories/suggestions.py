from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Suggestion

# Cap shared with the generator (background/suggestion_generation.py) so the
# list endpoint surfaces every active suggestion the generator may create,
# instead of under-showing (previously list_active capped at 5 while the
# generator allowed up to 10 active).
MAX_ACTIVE_SUGGESTIONS = 10


async def count_active(session: AsyncSession, user_id: UUID) -> int:
    """Return the number of active (non-dismissed, non-expired) suggestions."""
    now = datetime.now(UTC)
    result = await session.execute(
        select(func.count())
        .select_from(Suggestion)
        .where(
            Suggestion.user_id == user_id,
            Suggestion.dismissed == False,  # noqa: E712
            (Suggestion.expires_at == None) | (Suggestion.expires_at > now),  # noqa: E711
        )
    )
    return result.scalar_one()


async def list_active(session: AsyncSession, user_id: UUID) -> list[Suggestion]:
    now = datetime.now(UTC)
    result = await session.execute(
        select(Suggestion)
        .where(
            Suggestion.user_id == user_id,
            Suggestion.dismissed == False,  # noqa: E712
            (Suggestion.expires_at == None) | (Suggestion.expires_at > now),  # noqa: E711
        )
        .order_by(Suggestion.created_at.desc())
        .limit(MAX_ACTIVE_SUGGESTIONS)
    )
    return list(result.scalars().all())


async def dismiss(session: AsyncSession, suggestion_id: UUID, user_id: UUID) -> bool:
    item = await session.get(Suggestion, suggestion_id)
    if not item or item.user_id != user_id:
        return False
    item.dismissed = True
    await session.commit()
    return True


async def create_many(session: AsyncSession, user_id: UUID, items: list[dict]) -> None:
    expires = datetime.now(UTC) + timedelta(days=7)
    for item in items:
        s = Suggestion(
            user_id=user_id,
            text=item["text"],
            category=item.get("category", "general"),
            source=item.get("source", "model"),
            expires_at=expires,
        )
        session.add(s)
    await session.commit()


async def delete_expired(session: AsyncSession) -> int:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Suggestion).where(
                Suggestion.expires_at != None,  # noqa: E711
                Suggestion.expires_at <= datetime.now(UTC),
            )
        ),
    )
    await session.commit()
    return result.rowcount
