"""PostgreSQL practice ownership, row locks, retry uniqueness, and account erasure."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import engine
from app.models.orm import LearningPracticeEvent, Project, ProjectItem, User
from app.models.schemas.learning import LearningPracticeIn
from app.services.learning.practice import record_practice
from app.services.projects.crud import ProjectsError


def rows():
    user = User(id=uuid4(), email=f"{uuid4()}@example.com")
    project = Project(id=uuid4(), user_id=user.id, title="English", kind="language")
    item = ProjectItem(
        id=uuid4(), user_id=user.id, project_id=project.id, content="hello", list_title="Greetings"
    )
    return user, project, item


def body(attempt=None):
    return LearningPracticeIn(attempt_id=attempt or uuid4(), was_correct=True, completes_word=True)


@pytest.fixture(autouse=True)
def no_cache_io(monkeypatch):
    monkeypatch.setattr("app.services.learning.practice._invalidate_home_for_user", AsyncMock())


@pytest.mark.asyncio
async def test_locked_row_refresh_preserves_intervening_counts(db_session):
    user, project, item = rows()
    db_session.add_all([user, project, item])
    await db_session.flush()
    await db_session.execute(
        update(ProjectItem)
        .where(ProjectItem.id == item.id)
        .values(quiz_attempts=8, quiz_correct=6, review_count=3)
        .execution_options(synchronize_session=False)
    )
    assert item.quiz_attempts == 0
    updated, recorded, newly_mastered = await record_practice(
        db_session, user.id, project.id, item.id, body()
    )
    assert recorded and updated.quiz_attempts == 9 and updated.quiz_correct == 7
    assert updated.review_count == 4
    assert newly_mastered is True


@pytest.mark.asyncio
async def test_foreign_owner_and_mismatched_project_never_find_item(db_session):
    user, project, item = rows()
    other = User(id=uuid4(), email=f"{uuid4()}@example.com")
    db_session.add_all([user, project, item, other])
    await db_session.commit()
    # Expected authorization failures roll back and expire ORM instances.
    user_id, item_id = user.id, item.id
    for owner, project_id in [(other.id, project.id), (user.id, uuid4())]:
        with pytest.raises(ProjectsError) as error:
            await record_practice(db_session, owner, project_id, item_id, body())
        assert error.value.status_code == 404
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(LearningPracticeEvent)
            .where(LearningPracticeEvent.user_id == user_id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_account_deletion_cascades_practice_history(db_session):
    user, project, item = rows()
    db_session.add_all([user, project, item])
    await db_session.commit()
    user_id = user.id
    await record_practice(db_session, user_id, project.id, item.id, body())
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.flush()
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(LearningPracticeEvent)
            .where(LearningPracticeEvent.user_id == user_id)
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("same_attempt", [True, False])
async def test_concurrent_questions_do_not_double_count_retries_or_lose_outcomes(
    db_session, same_attempt
):
    # Separate committed fixtures let real independent connections contend on the
    # same row. Cleanup is explicit; the normal db_session fixture owns pool setup.
    user, project, item = rows()
    user_id, project_id, item_id = user.id, project.id, item.id
    async with AsyncSession(engine, expire_on_commit=False) as setup:
        setup.add_all([user, project, item])
        await setup.commit()
    attempt = uuid4()

    async def submit(attempt_id):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            _, recorded, newly_mastered = await record_practice(
                session, user_id, project_id, item_id, body(attempt_id)
            )
            return recorded, newly_mastered

    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(submit(attempt), submit(attempt if same_attempt else uuid4())),
            timeout=10,
        )
        async with AsyncSession(engine) as verify:
            saved = await verify.get(ProjectItem, item_id)
            count = await verify.scalar(
                select(func.count())
                .select_from(LearningPracticeEvent)
                .where(LearningPracticeEvent.user_id == user_id)
            )
            assert count == saved.quiz_attempts == saved.review_count == (1 if same_attempt else 2)
            assert sum(recorded for recorded, _ in outcomes) == count
            assert sum(newly for _, newly in outcomes) == (2 if same_attempt else 1)
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_attempt_identity_is_unique_per_owner_across_items(db_session):
    user, project, item = rows()
    another = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        content="goodbye",
        list_title="Greetings",
    )
    db_session.add_all([user, project, item, another])
    await db_session.commit()
    attempt = body()
    await record_practice(db_session, user.id, project.id, item.id, attempt)
    with pytest.raises(ProjectsError) as error:
        await record_practice(db_session, user.id, project.id, another.id, attempt)
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_replay_keeps_original_mastery_classification_after_later_review(db_session):
    user, project, item = rows()
    db_session.add_all([user, project, item])
    await db_session.commit()
    first, review = body(), body()
    assert (await record_practice(db_session, user.id, project.id, item.id, first))[2] is True
    assert (await record_practice(db_session, user.id, project.id, item.id, review))[2] is False
    current, recorded, newly_mastered = await record_practice(
        db_session, user.id, project.id, item.id, first
    )
    assert recorded is False and newly_mastered is True and current.review_count == 2
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(LearningPracticeEvent)
            .where(
                LearningPracticeEvent.user_id == user.id,
                LearningPracticeEvent.newly_mastered.is_(True),
            )
        )
        == 1
    )
