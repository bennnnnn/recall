"""Whole seed transaction tests with actual local SQL and post-commit effects."""

from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.orm import ProjectItem
from app.repositories import learning_catalog as catalog_repo
from app.services.learning import catalog_sync
from app.services.projects import path_seed
from app.tests.services.test_learning_catalog_reconciliation import (
    _deck,
    _saved_item,
)
from app.tests.services.test_learning_catalog_reconciliation import (
    catalog_sql as _catalog_sql,
)

catalog_sql = _catalog_sql


def _seed_environment(monkeypatch, sync, session, decks):
    @asynccontextmanager
    async def session_scope():
        try:
            yield session
        except Exception:
            sync.rollback()
            raise

    monkeypatch.setattr("app.core.db.SessionLocal", session_scope)
    monkeypatch.setattr(path_seed, "path_decks_for_language", lambda lang: decks)
    monkeypatch.setattr(catalog_sync, "_sync_decks", lambda: decks)
    invalidate = AsyncMock(side_effect=lambda user_id: sync.expire_all())
    monkeypatch.setattr("app.services.projects.common._invalidate_home_for_user", invalidate)
    return invalidate


@pytest.mark.asyncio
async def test_seed_refreshes_existing_adds_group_and_is_idempotent(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    deck = _deck()
    user, project, item = _saved_item(sync, deck)
    item_id = item.id
    item.definition = "Old definition"
    item.status = "learning"
    item.review_count = 7
    sync.commit()
    new = replace(deck, slug="appended-group", title="Appended group", sort_order=2)
    invalidate = _seed_environment(monkeypatch, sync, session, [deck, new])
    await path_seed.seed_language_path(None, user_id=user.id, project_id=project.id)
    rows = sync.scalars(select(ProjectItem).order_by(ProjectItem.list_title)).all()
    assert len(rows) == 2
    refreshed = sync.get(ProjectItem, item_id)
    assert refreshed.definition == deck.words[0].definition
    assert refreshed.status == "learning" and refreshed.review_count == 7
    assert project.learning_path == [deck.title, new.title]
    ids = {row.id for row in rows}
    session.commit.assert_awaited_once()
    invalidate.assert_awaited_once_with(user.id)
    await path_seed.seed_language_path(None, user_id=user.id, project_id=project.id)
    assert {row.id for row in sync.scalars(select(ProjectItem))} == ids
    session.commit.assert_awaited_once()
    invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_wrong_account_cannot_rewrite_project(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    user, project, item = _saved_item(sync, _deck())
    invalidate = _seed_environment(monkeypatch, sync, session, [_deck("Changed")])
    await path_seed.seed_language_path(None, user_id=uuid4(), project_id=project.id)
    sync.refresh(item)
    assert item.definition == _deck().words[0].definition
    session.commit.assert_not_awaited()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_failure_rolls_back_and_never_invalidates(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    user, project, item = _saved_item(sync, _deck())
    invalidate = _seed_environment(monkeypatch, sync, session, [_deck("Changed")])
    monkeypatch.setattr(
        catalog_repo, "insert_missing", AsyncMock(side_effect=RuntimeError("Write failed"))
    )
    await path_seed.seed_language_path(None, user_id=user.id, project_id=project.id)
    sync.refresh(item)
    assert item.definition == _deck().words[0].definition
    session.commit.assert_not_awaited()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_insert_ignores_collision_without_resetting_progress(catalog_sql):
    sync, session = catalog_sql
    user, project, item = _saved_item(sync, _deck())
    item.status = "mastered"
    item.review_count = 3
    sync.commit()
    from app.services.learning.catalog_items import word_values

    await catalog_repo.insert_missing(
        session,
        user_id=user.id,
        project_id=project.id,
        rows=[word_values(_deck(), _deck().words[0])],
    )
    sync.refresh(item)
    assert sync.query(ProjectItem).count() == 1
    assert item.status == "mastered" and item.review_count == 3
