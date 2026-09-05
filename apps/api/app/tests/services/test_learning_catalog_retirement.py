"""Retire old language content without touching current progress or other owners."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.orm import LearningPracticeEvent, Project, ProjectItem, QuizMissEvent
from app.services.learning import catalog_items
from app.services.projects import path_seed
from app.tests.services.test_learning_catalog_reconciliation import _deck, _item, _saved_item
from app.tests.services.test_learning_catalog_reconciliation import catalog_sql as _catalog_sql
from app.tests.services.test_learning_catalog_seed import _seed_environment

catalog_sql = _catalog_sql


def test_retired_rows_require_sync_even_when_all_active_words_are_present(monkeypatch):
    deck = _deck()
    monkeypatch.setattr(path_seed, "path_decks_for_language", lambda language: [deck])
    project = type("Project", (), {"target_language": "es", "learning_path": [deck.title]})()
    current = _item(deck)
    retired = _item(deck, catalog_entry_id=None, content="old word", list_title="Old group")
    assert path_seed.needs_catalog_sync(project, [current, retired])


def test_legacy_pair_does_not_adopt_or_suppress_current_word():
    deck = _deck()
    legacy = _item(deck, catalog_entry_id=None)
    changes = catalog_items.plan_catalog_changes([deck], [legacy])
    assert len(changes) == 1
    assert changes[0].item is None


@pytest.mark.asyncio
async def test_seed_deletes_retired_rows_and_keeps_current_progress_and_other_owners(
    catalog_sql, monkeypatch
):
    sync, session = catalog_sql
    LearningPracticeEvent.__table__.create(sync.get_bind())
    deck = _deck()
    user, project, current = _saved_item(sync, deck)
    other, other_project, other_item = _saved_item(sync, deck)
    current.status = "mastered"
    current.mastered = True
    current.review_count = 8
    current.quiz_attempts = 12
    current.mastered_at = datetime.now(UTC)
    retired_deck = replace(deck, slug="retired", title="Old group")
    retired = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        **catalog_items.word_values(retired_deck, retired_deck.words[0]),
    )
    unknown = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        list_title="Custom old group",
        content="old custom word",
    )
    other_language = Project(
        id=uuid4(),
        user_id=user.id,
        title="French",
        target_language="fr",
        learning_path=["Old"],
    )
    unrelated = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=other_language.id,
        list_title="Old",
        content="bonjour",
    )
    miss = QuizMissEvent(
        id=uuid4(), item_id=current.id, user_id=user.id, occurred_at=datetime.now(UTC)
    )
    practice = LearningPracticeEvent(
        id=uuid4(),
        attempt_id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        item_id=current.id,
        was_correct=True,
        completes_word=True,
        newly_mastered=True,
        occurred_at=datetime.now(UTC),
    )
    sync.add_all([retired, unknown, other_language, unrelated, miss, practice])
    sync.commit()
    expected_ids = {current.id, other_item.id, unrelated.id}
    expected_current_id = current.id
    miss_id, practice_id = miss.id, practice.id
    _seed_environment(monkeypatch, sync, session, [deck])

    await path_seed.seed_language_path(None, user_id=user.id, project_id=project.id)

    assert set(sync.scalars(select(ProjectItem.id))) == expected_ids
    saved = sync.get(ProjectItem, expected_current_id)
    assert saved.status == "mastered" and saved.review_count == 8 and saved.quiz_attempts == 12
    assert sync.get(QuizMissEvent, miss_id).item_id == expected_current_id
    assert sync.get(LearningPracticeEvent, practice_id).item_id == expected_current_id
    assert project.learning_path == [deck.title]


def test_read_projection_uses_current_group_without_mutating_saved_rows(catalog_sql, monkeypatch):
    sync, _ = catalog_sql
    deck = _deck()
    _, project, current = _saved_item(sync, deck)
    current.list_title = "Old renamed group"
    current.status = "mastered"
    current.review_count = 6
    sync.commit()
    monkeypatch.setattr(path_seed, "path_decks_for_language", lambda language: [deck])

    shown = path_seed.current_catalog_items(project, [current])

    assert len(shown) == 1 and shown[0] is not current
    assert shown[0].id == current.id and shown[0].list_title == deck.title
    assert shown[0].status == "mastered" and shown[0].review_count == 6
    assert current.list_title == "Old renamed group"
    sync.flush()
    sync.refresh(current)
    assert current.list_title == "Old renamed group"


@pytest.mark.asyncio
async def test_retired_collision_is_replaced_without_adopting_its_history(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    deck = _deck()
    user, project, old = _saved_item(sync, deck)
    old.catalog_entry_id = None
    old.status = "mastered"
    old.review_count = 10
    sync.commit()
    old_id, user_id, project_id = old.id, user.id, project.id
    _seed_environment(monkeypatch, sync, session, [deck])

    await path_seed.seed_language_path(None, user_id=user_id, project_id=project_id)

    rows = sync.scalars(select(ProjectItem).where(ProjectItem.project_id == project_id)).all()
    assert len(rows) == 1 and rows[0].id != old_id
    assert (
        rows[0].catalog_entry_id
        == catalog_items.word_values(deck, deck.words[0])["catalog_entry_id"]
    )
    assert rows[0].status == "new" and rows[0].review_count == 0


@pytest.mark.asyncio
async def test_retirement_rolls_back_if_reseeding_fails(catalog_sql, monkeypatch):
    from unittest.mock import AsyncMock

    from app.repositories import learning_catalog as catalog_repo

    sync, session = catalog_sql
    deck = _deck()
    user, project, old = _saved_item(sync, deck)
    old.catalog_entry_id = None
    sync.commit()
    old_id, user_id, project_id = old.id, user.id, project.id
    invalidate = _seed_environment(monkeypatch, sync, session, [deck])
    monkeypatch.setattr(
        catalog_repo, "insert_missing", AsyncMock(side_effect=RuntimeError("write failed"))
    )

    with pytest.raises(RuntimeError, match="write failed"):
        await path_seed.seed_language_path(None, user_id=user_id, project_id=project_id)

    assert sync.scalar(select(ProjectItem.id)) == old_id
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_cleanup_hides_retired_words_from_detail_and_recall(catalog_sql, monkeypatch):
    from unittest.mock import AsyncMock

    from app.core.config import Settings
    from app.services.projects import crud, prompt_context

    sync, _ = catalog_sql
    LearningPracticeEvent.__table__.create(sync.get_bind())
    deck = _deck()
    user, project, current = _saved_item(sync, deck)
    retired = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        list_title="Retired beginner group",
        content="retired beginner word",
    )
    sync.add(retired)
    sync.commit()
    retired_event = LearningPracticeEvent(
        id=uuid4(),
        attempt_id=uuid4(),
        item_id=retired.id,
        user_id=user.id,
        project_id=project.id,
        was_correct=True,
        completes_word=True,
        newly_mastered=True,
        occurred_at=datetime.now(UTC),
    )
    sync.add(retired_event)
    sync.commit()
    _, session = catalog_sql
    monkeypatch.setattr(path_seed, "path_decks_for_language", lambda language: [deck])
    enqueue = AsyncMock()
    monkeypatch.setattr(crud, "enqueue_language_path_job", enqueue)

    detail = await crud.get_project_detail(session, user, project.id, include_lists=True)
    assert detail is not None
    assert [group.list_title for group in detail["lists"]] == [deck.title]
    assert [item.id for group in detail["lists"] for item in group.items] == [current.id]
    assert all(day.completed_count == 0 for day in detail["daily_history"])
    enqueue.assert_awaited_once()
    block = await prompt_context.load_project_for_prompt(session, user.id, project.id, Settings())
    assert "retired beginner" not in block.lower()
    assert deck.words[0].content in block
    assert "today 0/" in block
    # Reading hides content while preserving it until the cleanup transaction.
    assert sync.get(ProjectItem, retired.id) is not None
