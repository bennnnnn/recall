from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User
from app.modules.job_search import publishing, tool, worker
from app.modules.job_search.models import JobSearchProfile


@pytest.fixture
async def account(db_session: AsyncSession) -> tuple[User, JobSearchProfile]:
    user = User(email=f"jobs-{uuid4()}@example.com", plan="pro", timezone="America/Los_Angeles")
    db_session.add(user)
    await db_session.flush()
    profile = JobSearchProfile(
        user_id=user.id,
        target_roles=["Backend Engineer"],
        skills=["Python", "SQL"],
        location="California, United States",
        included_locations=[{"country": "United States", "region": "California"}],
        excluded_locations=[],
        country="United States",
        salary_currency="USD",
        salary_min=None,
        years_experience=5,
        work_modes=["remote", "hybrid", "onsite"],
        experience_levels=["internship", "entry", "mid", "senior"],
        excluded_companies=[],
        result_count=10,
        frequency="weekdays",
        next_run_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(profile)
    await db_session.commit()
    return user, profile


@pytest.fixture
def durable_session(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(publishing, "SessionLocal", factory)
    monkeypatch.setattr(tool, "SessionLocal", factory)
