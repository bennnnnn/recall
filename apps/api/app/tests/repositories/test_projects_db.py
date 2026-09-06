"""Real-Postgres tests for app.repositories.projects — specifically the
partial unique indexes (one active language project per target language).
A mocked `AsyncSession` can't exercise a real DB constraint, so these use
the `db_session` fixture from conftest.py.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.orm import Project
from app.models.schemas import ProjectOut
from app.repositories import projects as projects_repo
from app.repositories import users as users_repo
from app.services.projects.crud import get_project_detail


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


@pytest.mark.asyncio
async def test_one_active_language_project_per_target_enforced_by_db(db_session):
    """Two active language rows for the same (user, target_language) must
    fail at the DB (migration 0065), not only in apply_project_actions."""
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
async def test_same_user_can_have_two_target_languages(db_session):
    user = await _make_user(db_session)
    await projects_repo.create(
        db_session, user_id=user.id, title="English", kind="language", target_language="en"
    )
    second = await projects_repo.create(
        db_session, user_id=user.id, title="Spanish", kind="language", target_language="es"
    )
    assert second.target_language == "es"


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
async def test_legacy_project_kinds_rejected_by_check_constraint(db_session):
    """Only language remains — trivia/general rows are blocked by ck_projects_kind."""
    user = await _make_user(db_session)
    user_id = user.id
    with pytest.raises(IntegrityError):
        await projects_repo.create(
            db_session, user_id=user_id, title="TypeScript · Programming", kind="general"
        )
    await db_session.rollback()
    with pytest.raises(IntegrityError):
        await projects_repo.create(
            db_session, user_id=user_id, title="General knowledge", kind="trivia"
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_get_project_detail_does_not_greenlet_after_catalog_titles(db_session):
    """Assigning learning_path on GET autoflushes; updated_at expires; ProjectOut 500s."""
    from app.content.vocab_catalog import path_decks_for_language

    user = await _make_user(db_session)
    project = await projects_repo.create(
        db_session, user_id=user.id, title="English", kind="language", target_language="en"
    )
    stored = list(project.learning_path or [])
    with patch(
        "app.services.projects.crud.enqueue_language_path_job",
        AsyncMock(),
    ):
        detail = await get_project_detail(db_session, user, project.id)

    assert detail is not None
    ProjectOut.model_validate(project)
    assert list(project.learning_path or []) == stored
    catalog = [deck.title for deck in path_decks_for_language("en")]
    assert detail["learning_path"] == catalog
    assert len(detail["path_progress"]) == len(catalog)
