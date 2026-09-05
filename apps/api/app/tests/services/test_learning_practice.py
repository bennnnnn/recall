"""Execute lesson transactions against offline SQL, with no provider dependencies."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import JSON, DateTime, create_engine, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.types import TypeDecorator

from app.models.orm import LearningPracticeEvent, Project, ProjectItem, QuizMissEvent, User
from app.models.schemas.learning import LearningPracticeIn
from app.repositories.project_items import count_stats_sql
from app.services.learning.practice import record_practice
from app.services.projects.crud import ProjectsError

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


class _UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


@pytest.fixture
def practice_sql():
    tables = [
        User.__table__,
        Project.__table__,
        ProjectItem.__table__,
        QuizMissEvent.__table__,
        LearningPracticeEvent.__table__,
    ]
    columns = [
        column
        for table in tables
        for column in table.c
        if isinstance(column.type, DateTime | JSONB)
    ]
    originals = [column.type for column in columns]
    for column in columns:
        column.type = JSON() if isinstance(column.type, JSONB) else _UTCDateTime()
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def transactional_connection(connection, record):
        connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def explicit_begin(connection):
        connection.exec_driver_sql("BEGIN")

    for table in tables:
        table.create(engine)
    try:
        with Session(engine, expire_on_commit=False) as real:
            session = AsyncMock(spec=AsyncSession)
            for name in ("execute", "scalar", "commit", "rollback", "flush", "refresh"):
                getattr(session, name).side_effect = getattr(real, name)
            session.add = MagicMock(side_effect=real.add)

            @asynccontextmanager
            async def nested():
                with real.begin_nested():
                    yield

            session.begin_nested.side_effect = nested
            user = User(id=uuid4(), email=f"{uuid4()}@example.com", name="Ada")
            project = Project(id=uuid4(), user_id=user.id, title="English", kind="language")
            item = ProjectItem(
                id=uuid4(),
                user_id=user.id,
                project_id=project.id,
                content="hello",
                list_title="Greetings",
            )
            real.add_all([user, project, item])
            real.commit()
            with patch("app.services.learning.practice._invalidate_home_for_user", AsyncMock()):
                yield real, session, user, project, item
    finally:
        engine.dispose()
        for column, original in zip(columns, originals, strict=True):
            column.type = original


def outcome(*, correct=True, complete=False, attempt_id=None):
    return LearningPracticeIn(
        attempt_id=attempt_id or uuid4(), was_correct=correct, completes_word=complete
    )


async def record(fixture, body, *, now=NOW):
    _, session, user, project, item = fixture
    return await record_practice(session, user.id, project.id, item.id, body, now=now)


@pytest.mark.asyncio
async def test_question_correctness_is_distinct_from_word_completion(practice_sql):
    real, _, _, _, item = practice_sql
    await record(practice_sql, outcome())
    assert item.quiz_attempts == item.quiz_correct == 1
    assert item.status == "learning"
    assert item.mastered_at is None
    assert item.review_count == 0
    assert real.scalar(select(func.count()).select_from(LearningPracticeEvent)) == 1


@pytest.mark.asyncio
async def test_every_wrong_question_is_recorded_even_when_already_learning(practice_sql):
    real, _, _, _, item = practice_sql
    await record(practice_sql, outcome(correct=False))
    await record(practice_sql, outcome(correct=False), now=NOW + timedelta(days=1))
    assert item.quiz_attempts == 2
    assert item.quiz_correct == 0
    assert item.last_incorrect_at == item.last_reviewed_at == NOW + timedelta(days=1)
    assert real.scalar(select(func.count()).select_from(QuizMissEvent)) == 2
    assert item.review_count == 0


@pytest.mark.asyncio
async def test_replay_returns_current_item_without_counting_twice(practice_sql):
    _, _, _, _, item = practice_sql
    first = outcome(correct=False)
    await record(practice_sql, first)
    await record(practice_sql, outcome(complete=True), now=NOW + timedelta(minutes=1))
    updated, recorded, newly_mastered = await record(
        practice_sql, first, now=NOW + timedelta(days=1)
    )
    assert recorded is False
    assert newly_mastered is False
    assert updated.status == "mastered"
    assert item.quiz_attempts == 2
    assert item.review_count == 1
    assert item.last_reviewed_at == NOW + timedelta(minutes=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["payload", "item"])
async def test_reused_attempt_cannot_apply_to_another_outcome(practice_sql, change):
    real, session, user, project, item = practice_sql
    body = outcome()
    await record(practice_sql, body)
    if change == "item":
        item = ProjectItem(
            id=uuid4(),
            user_id=user.id,
            project_id=project.id,
            content="goodbye",
            list_title="Greetings",
        )
        real.add(item)
        real.commit()
    else:
        body = outcome(correct=False, attempt_id=body.attempt_id)
    with pytest.raises(ProjectsError) as error:
        await record_practice(session, user.id, project.id, item.id, body, now=NOW)
    assert error.value.status_code == 409
    assert real.scalar(select(func.count()).select_from(LearningPracticeEvent)) == 1


@pytest.mark.asyncio
async def test_review_and_late_wrong_answer_preserve_first_mastery_and_schedule(practice_sql):
    _, _, _, _, item = practice_sql
    await record(practice_sql, outcome(complete=True))
    await record(practice_sql, outcome(complete=True), now=NOW + timedelta(days=1))
    due = item.due_at
    assert item.mastered_at == NOW
    assert item.last_completed_at == NOW + timedelta(days=1)
    assert item.review_count == 2
    await record(practice_sql, outcome(correct=False), now=NOW + timedelta(days=1, minutes=1))
    assert item.mastered is True
    assert item.status == "mastered"
    assert item.mastered_at == NOW
    assert item.review_count == 2
    assert item.due_at == due


@pytest.mark.asyncio
@pytest.mark.parametrize("other", ["user", "project"])
async def test_practice_never_crosses_ownership(practice_sql, other):
    real, session, user, project, item = practice_sql
    with pytest.raises(ProjectsError) as error:
        await record_practice(
            session,
            uuid4() if other == "user" else user.id,
            uuid4() if other == "project" else project.id,
            item.id,
            outcome(),
            now=NOW,
        )
    assert error.value.status_code == 404
    assert real.scalar(select(func.count()).select_from(LearningPracticeEvent)) == 0


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_event_and_progress_together(practice_sql):
    real, session, _, _, item = practice_sql
    session.commit.side_effect = RuntimeError("failed commit")
    with pytest.raises(RuntimeError, match="failed commit"):
        await record(practice_sql, outcome(complete=True))
    real.refresh(item)
    assert item.status == "new"
    assert item.quiz_attempts == 0
    assert real.scalar(select(func.count()).select_from(LearningPracticeEvent)) == 0


@pytest.mark.asyncio
async def test_sql_stats_count_reviewed_words_without_counting_them_as_new(practice_sql):
    _, session, user, project, _ = practice_sql
    await record(practice_sql, outcome(complete=True), now=NOW - timedelta(days=8))
    await record(practice_sql, outcome(complete=True))
    with patch(
        "app.repositories.project_items.start_of_today_utc", return_value=NOW.replace(hour=0)
    ):
        stats = await count_stats_sql(session, project.id, user.id, now=NOW)
    assert stats["completed_today"] == 1
    assert stats["attempted_today"] == 1
    assert stats["mastered_today"] == stats["newly_mastered_today"] == 0
    # SQLite aggregate typing can retain the original naive DateTime expression
    # after earlier tests compile the mapper; PostgreSQL returns an aware value.
    last_study = stats["last_study_at"]
    assert (last_study.replace(tzinfo=UTC) if last_study.tzinfo is None else last_study) == NOW


@pytest.mark.asyncio
async def test_clock_is_sampled_after_waiting_for_owned_row_lock(practice_sql):
    from app.repositories import learning_practice as repo

    _, _, _, _, item = practice_sql
    clock = MagicMock()
    clock.now.return_value = NOW
    original = repo.lock_owned_item

    async def delayed_lock(*args):
        locked = await original(*args)
        clock.now.return_value = NOW + timedelta(minutes=1)
        return locked

    with (
        patch.object(repo, "lock_owned_item", delayed_lock),
        patch("app.services.learning.practice.datetime", clock),
    ):
        await record(practice_sql, outcome(complete=True), now=None)
    assert item.last_reviewed_at == NOW + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_replay_heals_cache_after_committed_response_failure(practice_sql):
    _, session, _, _, _ = practice_sql
    body = outcome(complete=True)
    original = session.refresh.side_effect
    session.refresh.side_effect = RuntimeError("response refresh failed")
    with pytest.raises(RuntimeError, match="response refresh failed"):
        await record(practice_sql, body)
    session.refresh.side_effect = original
    with patch(
        "app.services.learning.practice._invalidate_home_for_user", AsyncMock()
    ) as invalidate:
        _, recorded, _ = await record(practice_sql, body)
    assert recorded is False
    invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_actual_sql_daily_items_keep_completed_reviews_on_original_day(practice_sql):
    from app.repositories.project_items import list_by_activity_date, list_missed_by_activity_date

    _, session, user, project, item = practice_sql
    await record(practice_sql, outcome(complete=True), now=NOW - timedelta(days=9))
    await record(practice_sql, outcome(complete=True), now=NOW - timedelta(days=1))
    await record(practice_sql, outcome(correct=False))
    start = NOW.replace(hour=0)
    previous = await list_by_activity_date(
        session, user.id, project.id, start=start - timedelta(days=1), end=start
    )
    assert previous == [item]
    assert (
        await list_by_activity_date(
            session, user.id, project.id, start=start, end=start + timedelta(days=1)
        )
        == []
    )
    assert await list_by_activity_date(
        session,
        user.id,
        project.id,
        start=start,
        end=start + timedelta(days=1),
        include_partial=True,
    ) == [item]
    assert await list_missed_by_activity_date(
        session, user.id, project.id, start=start, end=start + timedelta(days=1)
    ) == [item]
    assert (
        await list_by_activity_date(
            session, uuid4(), project.id, start=start - timedelta(days=1), end=start
        )
        == []
    )


@pytest.mark.asyncio
async def test_first_mastery_classification_is_immutable_across_reviews_and_replays(practice_sql):
    first = outcome(complete=True)
    review = outcome(complete=True)
    initial = await record(practice_sql, first)
    assert initial[2] is True
    reviewed = await record(practice_sql, review, now=NOW + timedelta(days=1))
    assert reviewed[2] is False
    retried_first = await record(practice_sql, first, now=NOW + timedelta(days=2))
    assert retried_first[1] is False and retried_first[2] is True
    assert retried_first[0].review_count == 2
    retried_review = await record(practice_sql, review, now=NOW + timedelta(days=2))
    assert retried_review[1] is False and retried_review[2] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("correct", [True, False])
async def test_incomplete_question_never_claims_first_mastery(practice_sql, correct):
    _, _, newly_mastered = await record(practice_sql, outcome(correct=correct))
    assert newly_mastered is False


@pytest.mark.asyncio
async def test_legacy_mastered_word_without_timestamp_is_a_review(practice_sql):
    real, _, _, _, item = practice_sql
    item.status, item.mastered = "mastered", True
    real.commit()
    _, _, newly_mastered = await record(practice_sql, outcome(complete=True))
    assert newly_mastered is False
