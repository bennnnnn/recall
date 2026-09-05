"""Catalog refresh regressions, using real local SQL without external services."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import JSON, create_engine, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.content.vocab_catalog import CatalogDeck, CatalogWord, word_id
from app.models.orm import Project, ProjectItem, QuizMissEvent, User, VocabDeck, VocabEntry
from app.repositories import learning_catalog as catalog_repo
from app.services.learning import catalog_items, catalog_sync
from app.services.projects import path_seed


@pytest.fixture
def catalog_sql(monkeypatch):
    engine = create_engine("sqlite://")
    for model in (User, Project, VocabDeck, VocabEntry, ProjectItem, QuizMissEvent):
        for column in model.__table__.c:
            if isinstance(column.type, JSONB):
                monkeypatch.setattr(column, "type", JSON())
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as sync:
        session = AsyncMock(spec=AsyncSession)
        session.execute.side_effect = sync.execute
        session.flush.side_effect = sync.flush
        session.commit.side_effect = sync.commit
        session.rollback.side_effect = sync.rollback
        yield sync, session
    engine.dispose()


def _deck(definition="A clear definition."):
    return CatalogDeck(
        "es",
        "test-stable",
        "Words",
        "Basics",
        "chapter",
        (
            CatalogWord(
                "casa",
                definition,
                "Esta casa es grande.\nVivo en una casa blanca.",
                part_of_speech="noun",
            ),
        ),
        1,
    )


def _item(deck, **changes):
    word = deck.words[0]
    values = dict(
        id=uuid4(),
        catalog_entry_id=word_id(deck, word),
        list_title=deck.title,
        content=word.content,
        definition=word.definition,
        example_sentence=word.example_sentence,
        ipa=word.ipa,
        part_of_speech=word.part_of_speech,
        simple_gloss=word.simple_gloss,
        vocabulary_kind="word",
        verb_kind=None,
        noun_kind=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_existing_word_with_old_content_needs_refresh(monkeypatch):
    deck = _deck()
    monkeypatch.setattr(path_seed, "path_decks_for_language", lambda lang: [deck])
    project = SimpleNamespace(target_language="es", learning_path=[deck.title])
    assert path_seed.needs_catalog_sync(project, [_item(deck, definition="Old shorthand")])
    assert not path_seed.needs_catalog_sync(project, [_item(deck)])


@pytest.mark.asyncio
async def test_catalog_updates_existing_content_without_replacing_id(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    old = _deck("Old shorthand")
    monkeypatch.setattr(catalog_sync, "_sync_decks", lambda: [old])
    await catalog_sync.ensure_catalog_rows(session)
    sync.commit()
    current = _deck()
    monkeypatch.setattr(catalog_sync, "_sync_decks", lambda: [current])
    await catalog_sync.ensure_catalog_rows(session)
    sync.expire_all()
    row = sync.get(VocabEntry, word_id(current, current.words[0]))
    assert row.definition == current.words[0].definition
    assert sync.query(VocabEntry).count() == 1


@pytest.mark.asyncio
async def test_sync_publishes_only_active_catalog(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    current = replace(_deck(), title="Updated title")
    monkeypatch.setattr(catalog_sync, "all_catalog_decks", lambda: [current])
    await catalog_sync.ensure_catalog_rows(session)
    assert sync.query(VocabEntry).count() == 1
    assert sync.get(VocabDeck, current.id).title == "Updated title"


@pytest.mark.parametrize(
    "field,value",
    [
        ("definition", "Old"),
        ("example_sentence", "Only one example."),
        ("ipa", "old"),
        ("part_of_speech", "verb"),
        ("simple_gloss", "old"),
        ("vocabulary_kind", "expression"),
        ("verb_kind", "action"),
        ("noun_kind", "proper"),
    ],
)
def test_each_content_field_triggers_refresh(monkeypatch, field, value):
    deck = _deck()
    assert catalog_items.plan_catalog_changes([deck], [_item(deck, **{field: value})])


def test_legacy_row_is_not_adopted_even_when_content_matches():
    deck = _deck()
    legacy = _item(deck, catalog_entry_id=None)
    changes = catalog_items.plan_catalog_changes([deck], [legacy])
    assert len(changes) == 1 and changes[0].item is None
    assert changes[0].values["catalog_entry_id"] == word_id(deck, deck.words[0])


def test_word_alone_never_moves_an_unrelated_user_item():
    deck = _deck()
    custom = _item(deck, catalog_entry_id=None, list_title="My own notes")
    changes = catalog_items.plan_catalog_changes([deck], [custom])
    assert len(changes) == 1 and changes[0].item is None
    assert custom.list_title == "My own notes"


def test_same_catalog_id_keeps_both_practice_rows_when_target_pair_occupied():
    deck = _deck()
    first = _item(deck)
    second = _item(deck, list_title="Older chapter", definition="Old definition")
    changes = catalog_items.plan_catalog_changes([deck], [first, second])
    assert len(changes) == 1 and changes[0].item.id == second.id
    assert "list_title" not in changes[0].values
    assert changes[0].values["definition"] == deck.words[0].definition


def _saved_item(sync, deck):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com")
    project = Project(
        id=uuid4(),
        user_id=user.id,
        title="Spanish",
        target_language="es",
        learning_path=[deck.title],
    )
    item = ProjectItem(
        id=uuid4(),
        user_id=user.id,
        project_id=project.id,
        **catalog_items.word_values(deck, deck.words[0]),
    )
    sync.add_all([user, project, item])
    sync.commit()
    return user, project, item


@pytest.mark.asyncio
async def test_content_update_preserves_intervening_practice_and_history(catalog_sql):
    sync, session = catalog_sql
    deck = _deck()
    user, project, item = _saved_item(sync, deck)
    # The ORM snapshot stays old while a practice writer commits fresh values.
    now = datetime.now(UTC).replace(tzinfo=None)
    practice = dict(
        status="mastered",
        mastered=True,
        mastered_at=now,
        last_reviewed_at=now,
        last_completed_at=now,
        last_incorrect_at=now - timedelta(days=1),
        review_count=9,
        quiz_attempts=12,
        quiz_correct=9,
        ease_factor=2.8,
        interval_days=14,
        due_at=now + timedelta(days=14),
        note="My note",
        pronunciation_url="https://example.com/audio.mp3",
    )
    sync.execute(
        update(ProjectItem)
        .where(ProjectItem.id == item.id)
        .values(**practice)
        .execution_options(synchronize_session=False)
    )
    miss = QuizMissEvent(id=uuid4(), item_id=item.id, user_id=user.id, occurred_at=now)
    sync.add(miss)
    sync.commit()
    assert item.review_count == 0
    await catalog_repo.update_contents(
        session,
        user_id=user.id,
        project_id=project.id,
        changes=[
            (item, {"definition": "Updated definition.", "example_sentence": "First.\nSecond."})
        ],
    )
    sync.commit()
    sync.refresh(item)
    assert item.definition == "Updated definition."
    assert all(getattr(item, key) == value for key, value in practice.items())
    assert sync.get(QuizMissEvent, miss.id).item_id == item.id


@pytest.mark.asyncio
async def test_content_update_rejects_other_account_and_project(catalog_sql):
    sync, session = catalog_sql
    user, project, item = _saved_item(sync, _deck())
    for user_id, project_id in [(uuid4(), project.id), (user.id, uuid4())]:
        await catalog_repo.update_contents(
            session,
            user_id=user_id,
            project_id=project_id,
            changes=[(item, {"definition": "Wrong owner"})],
        )
    sync.refresh(item)
    assert item.definition == _deck().words[0].definition
    assert await catalog_repo.lock_project(session, project.id, uuid4()) is None
    assert await catalog_repo.list_items(session, project.id, uuid4()) == []


@pytest.mark.asyncio
async def test_content_write_does_not_adopt_null_catalog_row(catalog_sql):
    sync, session = catalog_sql
    user, project, item = _saved_item(sync, _deck())
    item.catalog_entry_id = None
    sync.commit()
    sync.execute(
        update(ProjectItem)
        .where(ProjectItem.id == item.id)
        .values(definition="Personal revision")
        .execution_options(synchronize_session=False)
    )
    await catalog_repo.update_contents(
        session,
        user_id=user.id,
        project_id=project.id,
        changes=[(item, catalog_items.word_values(_deck(), _deck().words[0]))],
    )
    sync.refresh(item)
    assert item.definition == "Personal revision" and item.catalog_entry_id is None


@pytest.mark.asyncio
async def test_actual_active_catalog_content_is_published(catalog_sql):
    from app.content.vocab_catalog import path_decks_for_language

    sync, session = catalog_sql
    await catalog_sync.ensure_catalog_rows(session)
    for language in ("en", "es"):
        for deck in path_decks_for_language(language):
            for word in deck.words:
                row = sync.get(VocabEntry, word_id(deck, word))
                assert all(
                    getattr(row, name) == getattr(word, name)
                    for name in catalog_items.CONTENT_FIELDS
                )
                assert len(row.example_sentence.splitlines()) >= 2
