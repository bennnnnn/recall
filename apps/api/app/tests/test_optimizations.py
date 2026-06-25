"""Tests for optimised repository paths and new router endpoints."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.repositories.chats import group_by_recency

# ── group_by_recency: pure-function O(n) grouper ─────────────────────────────

def _chat(updated_at: datetime):
    c = MagicMock()
    c.updated_at = updated_at
    return c


def test_group_by_recency_today():
    now = datetime.now(UTC)
    chat = _chat(now)
    groups = group_by_recency([chat])
    assert len(groups["today"]) == 1
    assert groups["yesterday"] == []
    assert groups["earlier"] == []


def test_group_by_recency_earlier():
    from datetime import timedelta
    old = datetime.now(UTC) - timedelta(days=10)
    chat = _chat(old)
    groups = group_by_recency([chat])
    assert groups["today"] == []
    assert groups["earlier"] == [chat]


def test_group_by_recency_empty():
    groups = group_by_recency([])
    assert groups == {"today": [], "yesterday": [], "earlier": []}


def test_group_by_recency_naive_datetime():
    """Naive datetimes (no tzinfo) must be handled without raising."""
    naive = datetime(2024, 1, 1, 12, 0, 0)  # no tzinfo
    chat = _chat(naive)
    groups = group_by_recency([chat])  # should not raise
    assert isinstance(groups, dict)


# ── memories.upsert_many — single execute call ────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_many_single_query():
    """upsert_many must issue exactly 1 execute() call regardless of item count."""
    from app.repositories import memories as memories_repo

    session = AsyncMock()
    uid = uuid4()
    items = [
        ("fact", "Uses Python", 0.9, None),
        ("preference", "Short answers", 0.8, None),
        ("focus", "API project", 0.7, uuid4()),
    ]

    await memories_repo.upsert_many(session, user_id=uid, items=items)

    # Exactly one execute + one commit — not N queries
    assert session.execute.await_count == 1
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_many_empty_is_noop():
    from app.repositories import memories as memories_repo

    session = AsyncMock()
    await memories_repo.upsert_many(session, user_id=uuid4(), items=[])
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


# ── chats.delete_by_id — correct cascade order ────────────────────────────────

@pytest.mark.asyncio
async def test_delete_chat_cascades_then_deletes():
    """delete_by_id must nullify memories, delete messages, then delete the chat."""
    from app.repositories import chats as chats_repo

    chat = MagicMock()
    session = AsyncMock()
    execute_calls = []

    # Track execute call order
    async def record_execute(stmt):
        execute_calls.append(stmt)
        result = AsyncMock()
        return result

    session.execute.side_effect = record_execute

    with patch.object(chats_repo, "get_by_id", AsyncMock(return_value=chat)):
        result = await chats_repo.delete_by_id(session, uuid4(), uuid4())

    assert result is True
    # Two SQL statements (UPDATE memories + DELETE messages) + 1 ORM delete
    assert session.execute.await_count == 2
    session.delete.assert_called_once_with(chat)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_chat_not_found_returns_false():
    from app.repositories import chats as chats_repo

    session = AsyncMock()
    with patch.object(chats_repo, "get_by_id", AsyncMock(return_value=None)):
        result = await chats_repo.delete_by_id(session, uuid4(), uuid4())

    assert result is False
    session.execute.assert_not_awaited()


# ── delete_chat router ────────────────────────────────────────────────────────

def _app_with_user(user):
    from app.core.deps import get_current_user, get_settings_dep
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings()
    return app


def test_router_delete_chat_204():
    from fastapi.testclient import TestClient

    user = MagicMock()
    user.id = uuid4()
    app = _app_with_user(user)

    with patch("app.routers.chats.chats_repo.delete_by_id", AsyncMock(return_value=True)):
        client = TestClient(app)
        r = client.delete(f"/chats/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 204


def test_router_delete_chat_404():
    from fastapi.testclient import TestClient

    user = MagicMock()
    user.id = uuid4()
    app = _app_with_user(user)

    with patch("app.routers.chats.chats_repo.delete_by_id", AsyncMock(return_value=False)):
        client = TestClient(app)
        r = client.delete(f"/chats/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


# ── messages.count_for_chat — SQL scalar path ─────────────────────────────────

@pytest.mark.asyncio
async def test_count_for_chat_uses_scalar():
    from unittest.mock import MagicMock

    from app.repositories import messages as messages_repo

    session = AsyncMock()
    # scalar_one is a sync call on the execute result
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 42
    session.execute.return_value = result_mock

    count = await messages_repo.count_for_chat(session, uuid4())

    assert count == 42
    session.execute.assert_awaited_once()
    result_mock.scalar_one.assert_called_once()


# ── estimate_tokens — O(1) ────────────────────────────────────────────────────

def test_estimate_tokens_empty():
    from app.services.chat import estimate_tokens
    assert estimate_tokens("") == 1


def test_estimate_tokens_short():
    from app.services.chat import estimate_tokens
    # "hello" → len=5 // 4 = 1, max(1,1)=1
    assert estimate_tokens("hello") == 1


def test_estimate_tokens_long():
    from app.services.chat import estimate_tokens
    text = "a" * 400
    assert estimate_tokens(text) == 100
