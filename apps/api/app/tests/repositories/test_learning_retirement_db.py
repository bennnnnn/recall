"""Execute the frozen retirement migration inside rollback-only PostgreSQL fixtures."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.content.vocab_catalog import path_decks_for_language, word_id
from app.models.orm import (
    LearningPracticeEvent,
    Project,
    ProjectItem,
    QuizMissEvent,
    User,
    VocabDeck,
    VocabEntry,
)
from app.services.learning.catalog_items import word_values
from app.services.learning.catalog_sync import ensure_catalog_rows


async def run_retirement(session):
    path = Path(__file__).resolve().parents[3] / "alembic/versions/0080_retire_legacy_vocab.py"
    spec = importlib.util.spec_from_file_location("retirement_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def upgrade(connection):
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

    connection = await session.connection()
    await connection.run_sync(upgrade)


async def add_history(session, user, project, items):
    now = datetime.now(UTC)
    misses, practices = [], []
    for item in items:
        miss = QuizMissEvent(id=uuid4(), user_id=user.id, item_id=item.id, occurred_at=now)
        practice = LearningPracticeEvent(
            id=uuid4(),
            attempt_id=uuid4(),
            user_id=user.id,
            project_id=project.id,
            item_id=item.id,
            was_correct=True,
            completes_word=True,
            newly_mastered=True,
            occurred_at=now,
        )
        misses.append(miss.id)
        practices.append(practice.id)
        session.add_all([miss, practice])
    await session.flush()
    return misses, practices


async def remaining_ids(session, model, ids):
    return set((await session.scalars(select(model.id).where(model.id.in_(ids)))).all())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,saved_language,archived",
    [("en", "en", False), ("en", " EN ", True), ("es", "es", False), ("es", " ES ", True)],
)
async def test_retirement_deletes_old_rows_and_keeps_active_progress_and_goals(
    db_session, language, saved_language, archived
):
    session = db_session
    await ensure_catalog_rows(session)
    active_deck = path_decks_for_language(language)[0]
    user = User(id=uuid4(), email=f"{uuid4()}@example.test")
    old_deck = VocabDeck(
        id=uuid4(), target_language=language, slug=f"retired-{uuid4()}", title="Old beginner group"
    )
    session.add_all([user, old_deck])
    await session.flush()
    old_entries = [
        VocabEntry(id=uuid4(), deck_id=deck_id, content=f"old-{uuid4()}", definition="Old word")
        for deck_id in [old_deck.id, active_deck.id]
    ]
    project = Project(
        id=uuid4(),
        user_id=user.id,
        title="Saved class",
        target_language=saved_language,
        archived=archived,
        learning_path=["Old beginner group"],
        daily_goal=7,
        daily_goal_history=[{"effective_from": "2026-09-01", "goal": 7}],
    )
    session.add_all([project, *old_entries])
    await session.flush()
    now = datetime.now(UTC)
    progress = dict(
        status="mastered",
        mastered=True,
        mastered_at=now - timedelta(days=8),
        last_reviewed_at=now,
        last_completed_at=now,
        last_incorrect_at=now - timedelta(days=2),
        review_count=8,
        quiz_attempts=12,
        quiz_correct=8,
        ease_factor=2.7,
        interval_days=12,
        due_at=now + timedelta(days=12),
        note="Keep my note",
    )
    kept = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        **word_values(active_deck, active_deck.words[0]),
        **progress,
    )
    retired = [
        ProjectItem(
            id=uuid4(),
            user_id=user.id,
            project_id=project.id,
            catalog_entry_id=entry.id if entry else None,
            list_title="Old beginner group",
            content=f"old saved word {index}",
        )
        for index, entry in enumerate([*old_entries, None])
    ]
    session.add_all([kept, *retired])
    await session.flush()
    item_ids = [kept.id, *(item.id for item in retired)]
    miss_ids, practice_ids = await add_history(session, user, project, [kept, *retired])
    kept_entry_id = word_id(active_deck, active_deck.words[0])
    old_entry_ids = [entry.id for entry in old_entries]
    old_deck_id = old_deck.id

    for _ in range(2):
        await run_retirement(session)
        assert await remaining_ids(session, ProjectItem, item_ids) == {kept.id}
        assert await remaining_ids(session, QuizMissEvent, miss_ids) == {miss_ids[0]}
        assert await remaining_ids(session, LearningPracticeEvent, practice_ids) == {
            practice_ids[0]
        }
        assert await remaining_ids(session, VocabEntry, old_entry_ids) == set()
        assert await remaining_ids(session, VocabDeck, [old_deck_id]) == set()
        assert await remaining_ids(session, VocabEntry, [kept_entry_id]) == {kept_entry_id}
        assert await remaining_ids(session, VocabDeck, [active_deck.id]) == {active_deck.id}
        await session.refresh(kept)
        await session.refresh(project)
        assert all(getattr(kept, field) == value for field, value in progress.items())
        assert kept.catalog_entry_id == kept_entry_id
        assert project.learning_path == [deck.title for deck in path_decks_for_language(language)]
        assert project.daily_goal == 7
        assert project.daily_goal_history == [{"effective_from": "2026-09-01", "goal": 7}]
        assert project.archived == archived and project.target_language == saved_language


@pytest.mark.asyncio
async def test_retirement_leaves_unsupported_language_class_catalog_and_history_unchanged(
    db_session,
):
    session = db_session
    user = User(id=uuid4(), email=f"{uuid4()}@example.test")
    deck = VocabDeck(
        id=uuid4(), target_language="fr", slug=f"french-{uuid4()}", title="French group"
    )
    session.add_all([user, deck])
    await session.flush()
    entry = VocabEntry(id=uuid4(), deck_id=deck.id, content="bonjour", definition="French greeting")
    project = Project(
        id=uuid4(),
        user_id=user.id,
        title="French",
        target_language="fr",
        learning_path=["French group"],
        daily_goal=3,
    )
    session.add_all([entry, project])
    await session.flush()
    items = [
        ProjectItem(
            id=uuid4(),
            user_id=user.id,
            project_id=project.id,
            catalog_entry_id=catalog_id,
            list_title="French group",
            content=f"French item {index}",
            review_count=4,
        )
        for index, catalog_id in enumerate([entry.id, None])
    ]
    session.add_all(items)
    await session.flush()
    ids = {item.id for item in items}
    miss_ids, practice_ids = await add_history(session, user, project, items)

    await run_retirement(session)

    assert await remaining_ids(session, ProjectItem, ids) == ids
    assert await remaining_ids(session, VocabEntry, [entry.id]) == {entry.id}
    assert await remaining_ids(session, VocabDeck, [deck.id]) == {deck.id}
    assert await remaining_ids(session, QuizMissEvent, miss_ids) == set(miss_ids)
    assert await remaining_ids(session, LearningPracticeEvent, practice_ids) == set(practice_ids)
    await session.refresh(project)
    assert project.learning_path == ["French group"] and project.daily_goal == 3
    for index, item in enumerate(items):
        await session.refresh(item)
        assert item.catalog_entry_id == (entry.id if index == 0 else None)
        assert item.review_count == 4
