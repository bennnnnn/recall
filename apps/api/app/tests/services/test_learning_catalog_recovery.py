"""Empty English classes recover through the real worker, without live services."""

from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.background import handlers
from app.content.vocab_catalog import path_decks_for_language
from app.core import jobs
from app.core.config import Settings
from app.models.orm import LearningPracticeEvent, ProjectItem, User
from app.repositories import learning_catalog as catalog_repo
from app.services.learning import path, path_seed
from app.services.projects.crud import get_project_detail
from app.tests.services.test_learning_catalog_reconciliation import _saved_item
from app.tests.services.test_learning_catalog_reconciliation import (
    catalog_sql as _catalog_sql,
)
from app.tests.services.test_learning_catalog_seed import _seed_environment

catalog_sql = _catalog_sql


@pytest.fixture(autouse=True)
def clear_revision_cache():
    path_seed.catalog_seed_revision.cache_clear()
    yield
    path_seed.catalog_seed_revision.cache_clear()


def empty_english(catalog_sql, monkeypatch):
    sync, session = catalog_sql
    LearningPracticeEvent.__table__.create(sync.get_bind())
    decks = path_decks_for_language("en")
    user, project, item = _saved_item(sync, decks[0])
    sync.delete(item)
    project.target_language = "en"
    project.title = "English"
    project.learning_path = []
    sync.commit()
    _seed_environment(monkeypatch, sync, session, decks)
    return user.id, project.id, decks


async def dispatch_seed(monkeypatch, user_id, project_id):
    import json

    monkeypatch.setitem(jobs._HANDLERS, "language_path", handlers._handle_language_path)
    monkeypatch.setattr(jobs, "_RETRY_BACKOFF_S", 0)
    redis = AsyncMock()
    redis.set.return_value = True
    await jobs._process_one_entry(
        redis,
        Settings(),
        "1-0",
        {
            "type": "language_path",
            "payload": json.dumps({"user_id": str(user_id), "project_id": str(project_id)}),
            "dedupe_key": f"language_path:{project_id}",
        },
    )
    return redis


@pytest.mark.asyncio
async def test_transient_seed_failure_retries_before_success_ack(catalog_sql, monkeypatch):
    user_id, project_id, decks = empty_english(catalog_sql, monkeypatch)
    sync, session = catalog_sql
    monkeypatch.setattr(handlers, "_spend_capped", AsyncMock(return_value=False))
    original_insert = catalog_repo.insert_missing
    attempts = 0

    async def flaky_insert(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Transient database failure")
        await original_insert(*args, **kwargs)

    monkeypatch.setattr(catalog_repo, "insert_missing", flaky_insert)
    redis = await dispatch_seed(monkeypatch, user_id, project_id)

    assert attempts == 2
    rows = sync.scalars(select(ProjectItem)).all()
    assert len(rows) == sum(len(deck.words) for deck in decks) == 40
    assert {row.user_id for row in rows} == {user_id}
    assert {row.project_id for row in rows} == {project_id}
    redis.expire.assert_awaited_once()
    redis.xack.assert_awaited_once()
    redis.xadd.assert_not_awaited()
    detail = await get_project_detail(
        session, sync.get(User, user_id), project_id, include_lists=True
    )
    assert detail is not None
    assert len(detail["path_progress"]) == len(detail["lists"]) == 4
    assert sum(group.total for group in detail["path_progress"]) == 40
    assert sum(len(group.items) for group in detail["lists"]) == 40
    assert detail["up_next"] == decks[0].title


@pytest.mark.asyncio
async def test_curated_english_seed_does_not_depend_on_ai_spending(catalog_sql, monkeypatch):
    user_id, project_id, decks = empty_english(catalog_sql, monkeypatch)
    sync, _ = catalog_sql
    spending = AsyncMock(return_value=True)
    monkeypatch.setattr(handlers, "_spend_capped", spending)

    await dispatch_seed(monkeypatch, user_id, project_id)

    assert len(sync.scalars(select(ProjectItem)).all()) == sum(len(deck.words) for deck in decks)
    spending.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_failure_retries_invalidation_without_replacing_seeded_rows(
    catalog_sql, monkeypatch
):
    user_id, project_id, _ = empty_english(catalog_sql, monkeypatch)
    sync, session = catalog_sql
    saved_ids = set()

    async def invalidate(owner):
        assert owner == user_id
        ids = set(sync.scalars(select(ProjectItem.id)))
        if not saved_ids:
            saved_ids.update(ids)
            raise RuntimeError("Transient cache failure")
        assert ids == saved_ids

    invalidation = AsyncMock(side_effect=invalidate)
    monkeypatch.setattr("app.services.projects.common._invalidate_home_for_user", invalidation)
    redis = await dispatch_seed(monkeypatch, user_id, project_id)

    assert invalidation.await_count == 2
    assert len(saved_ids) == 40
    session.commit.assert_awaited_once()
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_exhausted_seed_failure_releases_dedupe_and_goes_to_dlq(catalog_sql, monkeypatch):
    user_id, project_id, _ = empty_english(catalog_sql, monkeypatch)
    sync, _ = catalog_sql
    failing = AsyncMock(side_effect=RuntimeError("Database unavailable"))
    monkeypatch.setattr(catalog_repo, "insert_missing", failing)

    redis = await dispatch_seed(monkeypatch, user_id, project_id)

    assert failing.await_count == jobs._MAX_ATTEMPTS
    assert sync.scalars(select(ProjectItem)).all() == []
    redis.expire.assert_not_awaited()
    redis.delete.assert_awaited_once()
    assert redis.xadd.await_args.args[0] == jobs.JOBS_DLQ_STREAM
    redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_key_bypasses_legacy_success_but_dedupes_same_catalog(monkeypatch):
    user_id, project_id = uuid4(), uuid4()
    redis = AsyncMock()
    done = {jobs.job_done_key(f"language_path:{project_id}")}

    async def claim(key, value, **kwargs):
        if key in done:
            return False
        done.add(key)
        return True

    redis.set.side_effect = claim
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: redis)
    seed = AsyncMock()
    monkeypatch.setitem(jobs._HANDLERS, "language_path", seed)
    for entry_id in ("1-0", "2-0"):
        await path.enqueue_language_path_job(user_id, project_id)
        fields = redis.xadd.await_args.args[1]
        await jobs._process_one_entry(redis, Settings(), entry_id, fields)

    seed.assert_awaited_once()
    keys = [call.args[1]["dedupe_key"] for call in redis.xadd.await_args_list]
    assert keys[0] == keys[1] != f"language_path:{project_id}"


def test_seed_revision_changes_when_catalog_content_changes(monkeypatch):
    decks = path_decks_for_language("en")
    original_revision = path_seed.catalog_seed_revision()
    changed = [
        replace(decks[0], words=(replace(decks[0].words[0], definition="Changed"),)),
        *decks[1:],
    ]
    monkeypatch.setattr(
        path_seed,
        "path_decks_for_language",
        lambda language: changed if language == "en" else path_decks_for_language(language),
    )
    path_seed.catalog_seed_revision.cache_clear()
    assert path_seed.catalog_seed_revision() != original_revision
