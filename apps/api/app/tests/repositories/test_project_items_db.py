"""Real-Postgres tests for app.repositories.project_items — list_recent_for_user's
ordering and apply_quiz_result's atomicity, neither of which a mocked
AsyncSession can exercise (a mock returns a canned result no matter what
statement was actually compiled and executed).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update as sql_update

from app.models.orm import Project, ProjectItem
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories import users as users_repo
from app.services.projects import items as project_items_service
from app.services.projects import quiz_grading


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


async def _make_project(session, user_id):
    return await projects_repo.create(
        session,
        user_id=user_id,
        title="Spanish",
        kind="language",
    )


def _build_item(user_id, project_id, *, created_at, content="word", list_title="General"):
    """Construct a ProjectItem with an explicit created_at (bypassing the
    repository's create(), which has no way to control it), so recency
    ordering is deterministic instead of racing the DB clock."""
    return ProjectItem(
        user_id=user_id,
        project_id=project_id,
        content=content,
        list_title=list_title,
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_list_recent_for_user_orders_by_recency_and_respects_limit(db_session):
    """BUG FIX regression: list_for_user orders by (list_title, status,
    created_at desc) before LIMIT, so a >limit deck isn't guaranteed to
    surface the newest items — apply_project_actions' match/dedup snapshot
    now uses list_recent_for_user instead, which orders by created_at desc
    only."""
    user = await _make_user(db_session)
    project = Project(user_id=user.id, title="English", kind="language")
    db_session.add(project)
    await db_session.flush()

    base = datetime(2026, 1, 1, tzinfo=UTC)
    items = [
        # Deliberately alphabetically-reversed content/list_title so a
        # (list_title, ...) ordering would NOT coincidentally produce the
        # same order as created_at desc.
        _build_item(
            user.id,
            project.id,
            created_at=base + timedelta(minutes=i),
            content=f"z-word-{i}",
            list_title="AAA",
        )
        for i in range(5)
    ]
    db_session.add_all(items)
    await db_session.flush()

    result = await project_items_repo.list_recent_for_user(db_session, user.id, limit=3)

    assert [i.content for i in result] == ["z-word-4", "z-word-3", "z-word-2"]


@pytest.mark.asyncio
async def test_list_recent_for_user_scopes_to_project(db_session):
    user = await _make_user(db_session)
    project_a = Project(user_id=user.id, title="A", kind="language")
    project_b = Project(user_id=user.id, title="B", kind="trivia")
    db_session.add_all([project_a, project_b])
    await db_session.flush()

    base = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.add_all(
        [
            _build_item(user.id, project_a.id, created_at=base, content="a-word"),
            _build_item(user.id, project_b.id, created_at=base, content="b-word"),
        ]
    )
    await db_session.flush()

    result = await project_items_repo.list_recent_for_user(
        db_session, user.id, project_id=project_a.id
    )

    assert [i.content for i in result] == ["a-word"]


@pytest.mark.asyncio
async def test_apply_quiz_result_increment_is_atomic_not_lost(db_session):
    """BUG FIX (was silent): quiz_attempts/quiz_correct were read into Python,
    incremented, and written back — a concurrent writer's update landing between
    the read and the write got silently clobbered (lost update). Simulate that
    "other request already landed" by bumping the row directly in SQL after
    `item` is loaded (so the in-memory object is now stale) and confirm
    apply_quiz_result's own increment builds on the true current row instead of
    overwriting it with a stale Python-computed value.
    """
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)
    item = await project_items_repo.create(
        db_session, user_id=user.id, project_id=project.id, content="hola"
    )
    assert item.quiz_attempts == 0
    assert item.quiz_correct == 0

    # A concurrent request's write landing after `item` was loaded but before
    # ours applies — `item` in memory still reflects the pre-bump counts.
    # `synchronize_session=False` keeps the ORM from eagerly syncing `item`'s
    # in-memory attributes to this write, so it stays genuinely stale, the way
    # a separate request's session would never see this one's update either.
    await db_session.execute(
        sql_update(ProjectItem)
        .where(ProjectItem.id == item.id)
        .values(quiz_attempts=5, quiz_correct=2)
        .execution_options(synchronize_session=False)
    )
    assert item.quiz_attempts == 0  # still stale in memory — the write bypassed it

    await quiz_grading.apply_quiz_result(db_session, item, is_correct=True, commit=False)

    # Under the old read-modify-write code this would land at 1 (0 + 1),
    # clobbering the concurrent writer's update to 5. The atomic SQL increment
    # must build on top of the row's true current value instead.
    assert item.quiz_attempts == 6
    assert item.quiz_correct == 3


def _frozen_datetime_cls(moment: datetime) -> type[datetime]:
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    return _Frozen


@pytest.mark.asyncio
async def test_apply_quiz_result_logs_every_miss_event_not_just_the_latest(db_session, monkeypatch):
    """BUG FIX (was silent): last_incorrect_at is a single mutable column, so a Day-4
    miss on an item already missed on Day-1 used to silently erase Day-1's record.
    Two misses on different days must produce two QuizMissEvent rows, and
    list_miss_events_for_items must return both — not just the latest.
    """
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)
    item = await project_items_repo.create(
        db_session, user_id=user.id, project_id=project.id, content="hola"
    )

    day1 = datetime(2026, 1, 1, 9, tzinfo=UTC)
    day4 = day1 + timedelta(days=3)

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(day1))
    await quiz_grading.apply_quiz_result(db_session, item, is_correct=False, commit=False)

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(day4))
    await quiz_grading.apply_quiz_result(db_session, item, is_correct=False, commit=False)

    # The mutable column only remembers the latest miss...
    assert item.last_incorrect_at == day4

    # ...but the event log remembers both.
    events_by_item = await project_items_repo.list_miss_events_for_items(db_session, [item.id])
    occurred_at = events_by_item[item.id]
    assert sorted(occurred_at) == [day1, day4]


@pytest.mark.asyncio
async def test_list_missed_by_activity_date_survives_a_later_miss_on_the_same_item(
    db_session, monkeypatch
):
    """BUG FIX (was silent): this day-detail page used to filter on the single
    mutable last_incorrect_at column, so a Day-4 miss on an item already missed
    on Day-1 made it silently vanish from Day-1's page. It must now still show
    up under Day-1 (via the event log) even though the column itself only
    points at Day-4.
    """
    user = await _make_user(db_session)
    project = await _make_project(db_session, user.id)
    item = await project_items_repo.create(
        db_session, user_id=user.id, project_id=project.id, content="hola"
    )

    day1 = datetime(2026, 1, 1, 9, tzinfo=UTC)
    day4 = day1 + timedelta(days=3)

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(day1))
    await quiz_grading.apply_quiz_result(db_session, item, is_correct=False, commit=False)

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(day4))
    await quiz_grading.apply_quiz_result(db_session, item, is_correct=False, commit=False)
    await db_session.flush()

    day1_page = await project_items_service.list_missed_by_activity_date(
        db_session, user.id, project.id, day1.date(), timezone_name="UTC"
    )
    day4_page = await project_items_service.list_missed_by_activity_date(
        db_session, user.id, project.id, day4.date(), timezone_name="UTC"
    )
    day2_page = await project_items_service.list_missed_by_activity_date(
        db_session, user.id, project.id, (day1 + timedelta(days=1)).date(), timezone_name="UTC"
    )

    assert [i.id for i in day1_page] == [item.id]
    assert [i.id for i in day4_page] == [item.id]
    assert day2_page == []
