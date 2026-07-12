"""Real-Postgres tests for app.repositories.project_items — specifically
list_recent_for_user's ordering, which a mocked AsyncSession can't exercise
(the mock returns a canned result no matter what ORDER BY was compiled).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.orm import Project, ProjectItem
from app.repositories import project_items as project_items_repo
from app.repositories import users as users_repo


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
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
