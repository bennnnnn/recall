"""Real-Postgres tests for app.repositories.projects — specifically the
partial unique index added by migration 0055 (at most one active
language/trivia project per user). A mocked `AsyncSession` can't exercise a
real DB constraint, so these use the `db_session` fixture from conftest.py.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.orm import Project
from app.repositories import projects as projects_repo
from app.repositories import users as users_repo


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


@pytest.mark.asyncio
async def test_one_active_language_project_per_user_enforced_by_db(db_session):
    """BUG FIX (was silent): "one language + one trivia project per user"
    (FEATURES.md) was only checked in-memory in apply_project_actions, which
    two near-concurrent project-sync jobs could both pass before either
    commits (at-least-once job redelivery, see core/jobs.py). The partial
    unique index from migration 0055 makes the DB itself refuse the second
    active row for the same (user_id, kind)."""
    user = await _make_user(db_session)
    user_id = user.id
    await projects_repo.create(db_session, user_id=user_id, title="English", kind="language")

    with pytest.raises(IntegrityError):
        await projects_repo.create(
            db_session, user_id=user_id, title="English (dup)", kind="language"
        )
    # rollback() expires previously loaded ORM objects (e.g. `user`); use the
    # id captured above rather than touching `user` again (a sync attribute
    # access after rollback would trigger an unawaited lazy-load and blow up
    # with MissingGreenlet).
    await db_session.rollback()

    rows = (
        (await db_session.execute(select(Project).where(Project.user_id == user_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "English"


@pytest.mark.asyncio
async def test_one_active_trivia_project_per_user_enforced_by_db(db_session):
    user = await _make_user(db_session)
    user_id = user.id
    await projects_repo.create(db_session, user_id=user_id, title="Trivia", kind="trivia")

    with pytest.raises(IntegrityError):
        await projects_repo.create(db_session, user_id=user_id, title="Trivia 2", kind="trivia")
    await db_session.rollback()

    rows = (
        (await db_session.execute(select(Project).where(Project.user_id == user_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_different_users_can_each_have_their_own_language_project(db_session):
    """The unique index is scoped per user_id — it must not block other users."""
    user_a = await _make_user(db_session)
    user_b = await _make_user(db_session)
    await projects_repo.create(db_session, user_id=user_a.id, title="English A", kind="language")
    # Must not raise.
    await projects_repo.create(db_session, user_id=user_b.id, title="English B", kind="language")


@pytest.mark.asyncio
async def test_archiving_frees_up_the_kind_for_a_new_active_project(db_session):
    """The unique index is scoped to non-archived rows — archiving the old
    project must free up the kind again for a new active one."""
    user = await _make_user(db_session)
    old = await projects_repo.create(
        db_session, user_id=user.id, title="Old English", kind="language"
    )
    await projects_repo.update(db_session, old, archived=True)

    # Must not raise — the old row is archived, so this is the only active one.
    new = await projects_repo.create(
        db_session, user_id=user.id, title="New English", kind="language"
    )
    assert new.id != old.id


@pytest.mark.asyncio
async def test_general_kind_projects_are_not_limited_to_one(db_session):
    """The index only scopes kind IN ('language', 'trivia') — 'general' kind
    projects (legacy, hidden-not-deleted per FEATURES.md) are unaffected."""
    user = await _make_user(db_session)
    await projects_repo.create(db_session, user_id=user.id, title="Notes 1", kind="general")
    # Must not raise.
    await projects_repo.create(db_session, user_id=user.id, title="Notes 2", kind="general")
