"""Owned practice event reads and locked item access."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import LearningPracticeEvent, Project, ProjectItem, User


async def lock_owned_item(
    session: AsyncSession, user_id: UUID, project_id: UUID, item_id: UUID
) -> ProjectItem | None:
    # Match account deletion's User-before-item lock order. Key-share permits
    # simultaneous practice while preventing deletion during the event insert.
    owner = await session.scalar(
        select(User.id).where(User.id == user_id).with_for_update(read=True, key_share=True)
    )
    if owner is None:
        return None
    stmt = (
        select(ProjectItem)
        .join(Project, Project.id == ProjectItem.project_id)
        .where(
            ProjectItem.id == item_id,
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            Project.user_id == user_id,
            Project.archived.is_(False),
        )
        .with_for_update(of=ProjectItem)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_attempt(
    session: AsyncSession, user_id: UUID, attempt_id: UUID
) -> LearningPracticeEvent | None:
    return (
        await session.execute(
            select(LearningPracticeEvent).where(
                LearningPracticeEvent.user_id == user_id,
                LearningPracticeEvent.attempt_id == attempt_id,
            )
        )
    ).scalar_one_or_none()


async def list_events(
    session: AsyncSession,
    project_ids: list[UUID],
    *,
    since: datetime | None = None,
) -> list[LearningPracticeEvent]:
    if not project_ids:
        return []
    stmt = select(LearningPracticeEvent).where(LearningPracticeEvent.project_id.in_(project_ids))
    if since is not None:
        stmt = stmt.where(LearningPracticeEvent.occurred_at >= since)
    return list(
        (
            await session.execute(
                stmt.order_by(LearningPracticeEvent.occurred_at, LearningPracticeEvent.id)
            )
        )
        .scalars()
        .all()
    )
