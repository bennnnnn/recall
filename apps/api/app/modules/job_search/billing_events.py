"""An entitlement expiration pauses searches; renewals never resume them implicitly."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_search.models import JobSearchProfile


async def suspend_on_expiration(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        update(JobSearchProfile)
        .where(JobSearchProfile.user_id == user_id, JobSearchProfile.status == "active")
        .values(
            status="paused", suspension_reason="pro_expired", revision=JobSearchProfile.revision + 1
        )
    )
