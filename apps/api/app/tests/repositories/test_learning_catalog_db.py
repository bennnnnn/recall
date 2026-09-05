"""Postgres coverage for content refresh versus independent practice writes."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.content.vocab_catalog import CatalogDeck, CatalogWord, word_id
from app.models.orm import Project, ProjectItem, QuizMissEvent, User
from app.repositories import learning_catalog as catalog_repo
from app.services.learning import catalog_sync
from app.services.learning.catalog_items import word_values


async def _rows(session, monkeypatch):
    deck = CatalogDeck(
        "es",
        f"test-{uuid4()}",
        "Test words",
        "Test",
        "chapter",
        (
            CatalogWord(
                "casa",
                "Edificio donde vive una persona.",
                "Mi casa es pequeña.\nEntramos en la casa.",
                part_of_speech="noun",
                noun_kind="common",
            ),
        ),
        1,
    )
    monkeypatch.setattr(catalog_sync, "_sync_decks", lambda: [deck])
    await catalog_sync.ensure_catalog_rows(session)
    user = User(id=uuid4(), email=f"{uuid4()}@example.com")
    project = Project(id=uuid4(), user_id=user.id, title="Spanish", target_language="es")
    session.add_all([user, project])
    await session.flush()
    await catalog_repo.insert_missing(
        session, user_id=user.id, project_id=project.id, rows=[word_values(deck, deck.words[0])]
    )
    item = (
        await session.execute(select(ProjectItem).where(ProjectItem.project_id == project.id))
    ).scalar_one()
    return user, project, item, deck


@pytest.mark.asyncio
async def test_content_refresh_keeps_intervening_practice_and_miss_history(db_session, monkeypatch):
    user, project, item, _ = await _rows(db_session, monkeypatch)
    item_id = item.id
    now = datetime.now(UTC)
    practice = dict(
        status="mastered",
        mastered=True,
        mastered_at=now - timedelta(days=8),
        last_completed_at=now,
        last_reviewed_at=now,
        review_count=8,
        quiz_attempts=12,
        quiz_correct=8,
        ease_factor=2.7,
        interval_days=12,
        due_at=now + timedelta(days=12),
        last_incorrect_at=now - timedelta(days=2),
    )
    # As with another session, the snapshot used by the content writer remains
    # stale after the practice update reaches the database.
    await db_session.execute(
        update(ProjectItem)
        .where(ProjectItem.id == item_id)
        .values(**practice)
        .execution_options(synchronize_session=False)
    )
    miss = QuizMissEvent(id=uuid4(), item_id=item_id, user_id=user.id, occurred_at=now)
    db_session.add(miss)
    await db_session.flush()
    assert item.review_count == 0
    await catalog_repo.update_contents(
        db_session,
        user_id=user.id,
        project_id=project.id,
        changes=[(item, {"definition": "Updated content.", "example_sentence": "One.\nTwo."})],
    )
    await db_session.refresh(item)
    assert item.id == item_id and item.definition == "Updated content."
    assert all(getattr(item, field) == value for field, value in practice.items())
    assert await db_session.get(QuizMissEvent, miss.id) is miss


@pytest.mark.asyncio
async def test_catalog_write_is_idempotent_and_owner_scoped(db_session, monkeypatch):
    user, project, item, deck = await _rows(db_session, monkeypatch)
    other = User(id=uuid4(), email=f"{uuid4()}@example.com")
    db_session.add(other)
    await db_session.flush()
    item.status = "learning"
    item.review_count = 3
    await db_session.flush()
    for _ in range(2):
        await catalog_repo.insert_missing(
            db_session,
            user_id=user.id,
            project_id=project.id,
            rows=[word_values(deck, deck.words[0])],
        )
    assert await catalog_repo.lock_project(db_session, project.id, other.id) is None
    assert await catalog_repo.list_items(db_session, project.id, other.id) == []
    await catalog_repo.update_contents(
        db_session,
        user_id=other.id,
        project_id=project.id,
        changes=[(item, {"definition": "Wrong owner"})],
    )
    await catalog_repo.insert_missing(
        db_session,
        user_id=other.id,
        project_id=project.id,
        rows=[{**word_values(deck, deck.words[0]), "content": "wrong-owner-word"}],
    )
    await db_session.refresh(item)
    count = await db_session.scalar(
        select(func.count()).select_from(ProjectItem).where(ProjectItem.project_id == project.id)
    )
    assert count == 1 and item.review_count == 3 and item.status == "learning"
    assert item.definition == deck.words[0].definition
    assert item.catalog_entry_id == word_id(deck, deck.words[0])


@pytest.mark.asyncio
async def test_content_write_does_not_adopt_null_catalog_row(db_session, monkeypatch):
    user, project, item, deck = await _rows(db_session, monkeypatch)
    item.catalog_entry_id = None
    await db_session.flush()
    await db_session.execute(
        update(ProjectItem)
        .where(ProjectItem.id == item.id)
        .values(definition="Learner's custom edit")
        .execution_options(synchronize_session=False)
    )
    await catalog_repo.update_contents(
        db_session,
        user_id=user.id,
        project_id=project.id,
        changes=[(item, word_values(deck, deck.words[0]))],
    )
    await db_session.refresh(item)
    assert item.definition == "Learner's custom edit"
    assert item.catalog_entry_id is None


@pytest.mark.asyncio
async def test_runtime_retirement_cascades_only_retired_owned_language_history(
    db_session, monkeypatch
):
    from app.models.orm import LearningPracticeEvent

    user, project, current, deck = await _rows(db_session, monkeypatch)
    other, other_project, other_item, _ = await _rows(db_session, monkeypatch)
    retired = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        list_title="Retired",
        content="old word",
    )
    outside_project = Project(
        id=uuid4(),
        user_id=user.id,
        title="French",
        target_language="fr",
    )
    outside_item = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=outside_project.id,
        list_title="Other language",
        content="bonjour",
    )
    current.status = "mastered"
    current.review_count = 7
    db_session.add_all([retired, outside_project, outside_item])
    await db_session.flush()
    now = datetime.now(UTC)
    misses = [
        QuizMissEvent(id=uuid4(), item_id=item.id, user_id=user.id, occurred_at=now)
        for item in [current, retired]
    ]
    events = [
        LearningPracticeEvent(
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
        for item in [current, retired]
    ]
    db_session.add_all([*misses, *events])
    await db_session.flush()
    current_id, retired_id, outside_id, other_id = (
        current.id,
        retired.id,
        outside_item.id,
        other_item.id,
    )
    active_ids = [word_id(deck, deck.words[0])]
    await catalog_repo.delete_retired(
        db_session,
        user_id=other.id,
        project_id=project.id,
        active_ids=active_ids,
    )
    assert (
        await db_session.scalar(select(ProjectItem.id).where(ProjectItem.id == retired_id))
        == retired_id
    )
    await catalog_repo.delete_retired(
        db_session,
        user_id=user.id,
        project_id=outside_project.id,
        active_ids=active_ids,
    )
    assert (
        await db_session.scalar(select(ProjectItem.id).where(ProjectItem.id == outside_id))
        == outside_id
    )
    assert await catalog_repo.lock_project(db_session, project.id, user.id) is project
    await catalog_repo.delete_retired(
        db_session,
        user_id=user.id,
        project_id=project.id,
        active_ids=active_ids,
    )
    assert (
        await db_session.scalar(select(ProjectItem.id).where(ProjectItem.id == retired_id)) is None
    )
    assert set(
        (
            await db_session.scalars(
                select(ProjectItem.id).where(ProjectItem.id.in_([current_id, other_id, outside_id]))
            )
        ).all()
    ) == {current_id, other_id, outside_id}
    assert (
        await db_session.scalar(select(QuizMissEvent.id).where(QuizMissEvent.id == misses[1].id))
        is None
    )
    assert (
        await db_session.scalar(
            select(LearningPracticeEvent.id).where(LearningPracticeEvent.id == events[1].id)
        )
        is None
    )
    assert await db_session.get(QuizMissEvent, misses[0].id) is misses[0]
    assert await db_session.get(LearningPracticeEvent, events[0].id) is events[0]
    await db_session.refresh(current)
    assert current.status == "mastered" and current.review_count == 7
