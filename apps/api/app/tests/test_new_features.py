"""Tests for new features: todos, search, seed."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.tests.test_routers import _app_with_user, _fake_user

_DUE_AT = "2026-08-30T18:00:00Z"

# ── todos router ────────────────────────────────────────────────────────────


def test_list_todos_empty():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.modules.todos.crud.todos_repo.list_for_user", AsyncMock(return_value=[])):
        client = TestClient(app)
        r = client.get("/todos", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_list_todos_returns_items():
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Buy milk"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.modules.todos.crud.todos_repo.list_for_user", AsyncMock(return_value=[todo_mock])
    ):
        client = TestClient(app)
        r = client.get("/todos", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["content"] == "Buy milk"


def test_list_todos_passes_pagination_and_clamps_limit():
    """GET /todos exposes limit/offset (forward-compatible) and clamps the page
    so a caller can't request an unbounded scan. Default is 1000, not 200, so a
    heavy user no longer silently loses todos past the old cap."""
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.modules.todos.crud.todos_repo.list_for_user", AsyncMock(return_value=[])
    ) as list_mock:
        client = TestClient(app)
        # explicit pagination is forwarded
        client.get("/todos?limit=50&offset=10", headers={"Authorization": "Bearer tok"})
        _args, kwargs = list_mock.call_args
        assert kwargs["limit"] == 50
        assert kwargs["offset"] == 10

        # over-large limit is clamped to the max (1000); negative offset to 0
        list_mock.reset_mock()
        client.get("/todos?limit=99999&offset=-5", headers={"Authorization": "Bearer tok"})
        _args, kwargs = list_mock.call_args
        assert kwargs["limit"] == 1000
        assert kwargs["offset"] == 0


def test_create_todo():
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Test todo"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = None
    todo_mock.sort_order = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user()
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()
    with (
        patch("app.modules.todos.crud.todos_repo.create", AsyncMock(return_value=todo_mock)),
        patch("app.modules.todos.crud.home_service.invalidate_home_cache", invalidate_mock),
    ):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "Test todo", "due_at": _DUE_AT},
        )
    assert r.status_code == 201
    assert r.json()["content"] == "Test todo"
    invalidate_mock.assert_awaited_once_with(user.id)


def test_create_todo_with_chat_id():
    from fastapi.testclient import TestClient

    tid = uuid4()
    cid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "From chat"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = None
    todo_mock.sort_order = None
    todo_mock.chat_id = cid
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user()
    app = _app_with_user(user)
    # The router now verifies chat ownership before linking a todo to it
    # (cross-user FK guard). Mock the chat lookup so the owned-chat path
    # reaches todo creation.
    chat_mock = MagicMock()
    chat_mock.id = cid
    chat_mock.user_id = user.id
    with (
        patch("app.modules.todos.crud.todos_repo.create", AsyncMock(return_value=todo_mock)),
        patch("app.modules.todos.crud.chats_repo.get_by_id", AsyncMock(return_value=chat_mock)),
    ):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "From chat", "chat_id": str(cid), "due_at": _DUE_AT},
        )
    assert r.status_code == 201


def test_create_todo_empty_content_fails():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    client = TestClient(app)
    r = client.post(
        "/todos",
        headers={"Authorization": "Bearer tok"},
        json={"content": ""},
    )
    assert r.status_code == 422


def test_create_todo_with_other_users_chat_id_rejected():
    from fastapi.testclient import TestClient

    cid = uuid4()
    user = _fake_user()
    app = _app_with_user(user)
    # chats_repo.get_by_id returns None → the chat doesn't belong to this user
    # (or doesn't exist). The cross-user FK guard must reject with 400 rather
    # than silently linking the todo to a foreign chat.
    with patch("app.modules.todos.crud.chats_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "x", "chat_id": str(cid), "due_at": _DUE_AT},
        )
    assert r.status_code == 400
    assert "Chat not found" in r.json()["detail"]


def test_create_todo_with_unowned_chat_id_404s():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.modules.todos.crud.chats_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "x", "chat_id": str(uuid4()), "due_at": _DUE_AT},
        )
    assert r.status_code == 400


def test_update_todo():
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Updated"
    todo_mock.topic = "General"
    todo_mock.checked = True
    todo_mock.due_at = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user()
    app = _app_with_user(user)
    with (
        patch("app.modules.todos.crud.todos_repo.get_by_id", AsyncMock(return_value=todo_mock)),
        patch("app.modules.todos.crud.todos_repo.update", AsyncMock(return_value=todo_mock)),
    ):
        client = TestClient(app)
        r = client.patch(
            f"/todos/{tid}",
            headers={"Authorization": "Bearer tok"},
            json={"checked": True},
        )
    assert r.status_code == 200
    assert r.json()["checked"] is True


def test_update_todo_not_found():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.modules.todos.crud.todos_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.patch(
            f"/todos/{uuid4()}",
            headers={"Authorization": "Bearer tok"},
            json={"checked": True},
        )
    assert r.status_code == 404


def test_delete_todo():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.modules.todos.crud.todos_repo.delete_by_id", AsyncMock(return_value=True)):
        client = TestClient(app)
        r = client.delete(
            f"/todos/{uuid4()}",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 204


def test_delete_todo_not_found():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.modules.todos.crud.todos_repo.delete_by_id", AsyncMock(return_value=False)):
        client = TestClient(app)
        r = client.delete(
            f"/todos/{uuid4()}",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 404


def test_delete_todo_topic_batches_list_delete():
    """DELETE /todos/topic/{topic} removes a whole list in one call (only
    items without a due_at — lists, not reminders — per delete_by_topic)."""
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with (
        patch(
            "app.modules.todos.crud.todos_repo.delete_by_topic", AsyncMock(return_value=5)
        ) as delete_by_topic,
        patch("app.modules.todos.crud.home_service.invalidate_home_cache", AsyncMock()),
    ):
        client = TestClient(app)
        r = client.delete(
            "/todos/topic/Groceries",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 204
    delete_by_topic.assert_awaited_once()
    # Topic is passed through case-insensitively to the repo.
    assert delete_by_topic.call_args.args[2] == "Groceries"


def test_delete_todo_topic_not_found():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.modules.todos.crud.todos_repo.delete_by_topic", AsyncMock(return_value=0)):
        client = TestClient(app)
        r = client.delete(
            "/todos/topic/Nope",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 404


# ── todos router: due_at normalization ─────────────────────────────────────


def test_create_todo_normalizes_naive_due_at_to_user_timezone():
    """A naive due_at from the client must be interpreted in the user's
    timezone, not server time. Without normalization, a naive "9am" is
    stored as 9am UTC and reminders fire at the wrong wall-clock hour for
    any user not on UTC.
    """
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Test"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = None
    todo_mock.sort_order = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    # User in America/New_York (UTC-5 in EST).
    user = _fake_user(timezone="America/New_York")
    app = _app_with_user(user)
    create_mock = AsyncMock(return_value=todo_mock)
    with (
        patch("app.modules.todos.crud.todos_repo.create", create_mock),
        patch("app.modules.todos.crud.home_service.invalidate_home_cache", AsyncMock()),
    ):
        client = TestClient(app)
        # Naive 9:00 — should be interpreted as 9:00 America/New_York -> 14:00 UTC.
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "Test", "due_at": "2025-01-15T09:00:00"},
        )
    assert r.status_code == 201
    # The repo must receive a tz-aware UTC datetime.
    due_at = create_mock.await_args.kwargs["due_at"]
    assert due_at is not None
    assert due_at.tzinfo is not None
    # 9:00 EST (UTC-5) = 14:00 UTC.
    assert due_at.hour == 14


def test_create_todo_accepts_plain_undated_item():
    """A plain To-do is valid without a date."""
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Test"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = None
    todo_mock.recurrence_rule = None
    todo_mock.sort_order = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now
    user = _fake_user()
    app = _app_with_user(user)
    create_mock = AsyncMock(return_value=todo_mock)
    with (
        patch("app.modules.todos.crud.todos_repo.create", create_mock),
        patch("app.modules.todos.crud.home_service.invalidate_home_cache", AsyncMock()),
    ):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "Test"},
        )
    assert r.status_code == 201
    assert create_mock.await_args.kwargs["due_at"] is None
    assert create_mock.await_args.kwargs["topic"] == "General"


def test_update_todo_can_clear_due_at_and_repeat():
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Test"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = now
    todo_mock.recurrence_rule = "weekly"
    todo_mock.sort_order = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user()
    app = _app_with_user(user)
    updated_mock = MagicMock()
    updated_mock.id = tid
    updated_mock.content = "Test"
    updated_mock.topic = "General"
    updated_mock.checked = False
    updated_mock.due_at = None
    updated_mock.recurrence_rule = None
    updated_mock.sort_order = None
    updated_mock.chat_id = None
    updated_mock.created_at = now
    updated_mock.updated_at = now
    update_mock = AsyncMock(return_value=updated_mock)
    with (
        patch("app.modules.todos.crud.todos_repo.get_by_id", AsyncMock(return_value=todo_mock)),
        patch("app.modules.todos.crud.todos_repo.update", update_mock),
        patch("app.modules.todos.crud.home_service.invalidate_home_cache", AsyncMock()),
    ):
        client = TestClient(app)
        r = client.patch(
            f"/todos/{tid}",
            headers={"Authorization": "Bearer tok"},
            json={"due_at": None},
        )
    assert r.status_code == 200
    assert update_mock.await_args.kwargs["due_at"] is None
    assert update_mock.await_args.kwargs["recurrence_rule"] is None


def test_update_todo_normalizes_naive_due_at():
    """PATCH /todos/{id} must also normalize a naive due_at to the user's timezone."""
    from fastapi.testclient import TestClient

    tid = uuid4()
    now = datetime.now(UTC)
    todo_mock = MagicMock()
    todo_mock.id = tid
    todo_mock.content = "Updated"
    todo_mock.topic = "General"
    todo_mock.checked = False
    todo_mock.due_at = None
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user(timezone="Asia/Tokyo")  # UTC+9
    app = _app_with_user(user)
    update_mock = AsyncMock(return_value=todo_mock)
    with (
        patch("app.modules.todos.crud.todos_repo.get_by_id", AsyncMock(return_value=todo_mock)),
        patch("app.modules.todos.crud.todos_repo.update", update_mock),
        patch("app.modules.todos.crud.home_service.invalidate_home_cache", AsyncMock()),
    ):
        client = TestClient(app)
        # Naive 9:00 — should be interpreted as 9:00 Asia/Tokyo -> 0:00 UTC.
        r = client.patch(
            f"/todos/{tid}",
            headers={"Authorization": "Bearer tok"},
            json={"due_at": "2025-01-15T09:00:00"},
        )
    assert r.status_code == 200
    due_at = update_mock.await_args.kwargs["due_at"]
    assert due_at is not None
    assert due_at.tzinfo is not None
    # 9:00 JST (UTC+9) = 0:00 UTC.
    assert due_at.hour == 0


def test_projects_routes_are_gone():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/projects").status_code == 404
    assert client.post("/projects", json={"title": "Spanish"}).status_code == 404


# ── search router ───────────────────────────────────────────────────────────


def test_search_returns_results():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    fake_results = [
        {
            "match_type": "message",
            "message_id": uuid4(),
            "chat_id": uuid4(),
            "chat_title": "Test Chat",
            "content": "…hello world…",
            "role": "user",
            "created_at": datetime.now(UTC),
        }
    ]
    with patch(
        "app.modules.search.api.search_service.search_conversations",
        AsyncMock(return_value=(fake_results, 1)),
    ):
        client = TestClient(app)
        r = client.get(
            "/search?q=hello",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["chat_title"] == "Test Chat"


def test_search_returns_empty():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.modules.search.api.search_service.search_conversations",
        AsyncMock(return_value=([], 0)),
    ):
        client = TestClient(app)
        r = client.get(
            "/search?q=nonexistent",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_search_empty_query_fails():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    client = TestClient(app)
    r = client.get("/search?q=", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 422


def test_search_single_char_query_fails():
    """1-char queries defeat the trigram index — require at least 2 chars."""
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    client = TestClient(app)
    r = client.get("/search?q=a", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 422


def test_search_respects_limit():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    fake_results = [
        {
            "match_type": "message",
            "message_id": uuid4(),
            "chat_id": uuid4(),
            "chat_title": "Chat",
            "content": "…x…",
            "role": "assistant",
            "created_at": datetime.now(UTC),
        }
        for _ in range(5)
    ]
    with patch(
        "app.modules.search.api.search_service.search_conversations",
        AsyncMock(return_value=(fake_results, 42)),  # total=42, but only 5 returned
    ):
        client = TestClient(app)
        r = client.get(
            "/search?q=xx&limit=5",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 42  # real total, not limited
    assert len(data["results"]) == 5


# ── search repository snippet ───────────────────────────────────────────────


def test_search_snippet_exact_match():
    from app.modules.search.repository import _snippet

    content = "The quick brown fox jumps over the lazy dog"
    result = _snippet(content, "fox", 120)
    assert "fox" in result


def test_search_snippet_no_match():
    from app.modules.search.repository import _snippet

    content = "Hello world"
    result = _snippet(content, "zzz", 120)
    assert len(result) <= 120


def test_search_snippet_truncation():
    from app.modules.search.repository import _snippet

    content = "a" * 300 + "needle" + "b" * 300
    result = _snippet(content, "needle", 120)
    assert "needle" in result
    # Expect at most: 40 (prefix) + len(query) + 80 (suffix) + 2 (… markers) ≈ 128
    assert len(result) <= 130


# ── todos repository ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_todos_repo_create():
    from app.modules.todos.repository import create

    todo_mock = MagicMock()
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with (
        patch("app.modules.todos.repository.next_sort_order", AsyncMock(return_value=1)),
        patch("app.modules.todos.repository.TodoItem", return_value=todo_mock),
    ):
        result = await create(session, user_id=uuid4(), content="Task 1")
    assert result is todo_mock
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_todos_repo_create_commit_false_flushes_without_commit():
    from app.modules.todos.repository import create

    todo_mock = MagicMock()
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    with (
        patch("app.modules.todos.repository.next_sort_order", AsyncMock(return_value=1)),
        patch("app.modules.todos.repository.TodoItem", return_value=todo_mock),
    ):
        result = await create(session, user_id=uuid4(), content="Task 1", commit=False)
    assert result is todo_mock
    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_todos_repo_update_unchecks():
    from app.modules.todos.repository import update

    todo = MagicMock()
    todo.checked = True
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    updated = await update(session, todo, checked=False)
    assert updated.checked is False
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_todos_repo_delete_not_found():
    from app.modules.todos.repository import delete_by_id

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)

    result = await delete_by_id(session, uuid4(), uuid4())
    assert result is False
