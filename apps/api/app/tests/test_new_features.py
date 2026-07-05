"""Tests for new features: todos, search, suggestions, seed."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import (
    SuggestionGenerationResult,
    SuggestionItem,
)
from app.tests.test_routers import _app_with_user, _fake_user

# ── todos router ────────────────────────────────────────────────────────────


def test_list_todos_empty():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.todos.todos_repo.list_for_user", AsyncMock(return_value=[])):
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
    with patch("app.routers.todos.todos_repo.list_for_user", AsyncMock(return_value=[todo_mock])):
        client = TestClient(app)
        r = client.get("/todos", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["content"] == "Buy milk"


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
    todo_mock.chat_id = None
    todo_mock.created_at = now
    todo_mock.updated_at = now

    user = _fake_user()
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()
    with (
        patch("app.routers.todos.todos_repo.create", AsyncMock(return_value=todo_mock)),
        patch("app.routers.todos.home_service.invalidate_home_cache", invalidate_mock),
    ):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "Test todo"},
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
        patch("app.routers.todos.todos_repo.create", AsyncMock(return_value=todo_mock)),
        patch("app.routers.todos.chats_repo.get_by_id", AsyncMock(return_value=chat_mock)),
    ):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "From chat", "chat_id": str(cid)},
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
    with patch("app.routers.todos.chats_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "x", "chat_id": str(cid)},
        )
    assert r.status_code == 400
    assert "Chat not found" in r.json()["detail"]


def test_create_todo_with_unowned_chat_id_404s():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.todos.chats_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.post(
            "/todos",
            headers={"Authorization": "Bearer tok"},
            json={"content": "x", "chat_id": str(uuid4())},
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
        patch("app.routers.todos.todos_repo.get_by_id", AsyncMock(return_value=todo_mock)),
        patch("app.routers.todos.todos_repo.update", AsyncMock(return_value=todo_mock)),
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
    with patch("app.routers.todos.todos_repo.get_by_id", AsyncMock(return_value=None)):
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
    with patch("app.routers.todos.todos_repo.delete_by_id", AsyncMock(return_value=True)):
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
    with patch("app.routers.todos.todos_repo.delete_by_id", AsyncMock(return_value=False)):
        client = TestClient(app)
        r = client.delete(
            f"/todos/{uuid4()}",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 404


# ── projects router ─────────────────────────────────────────────────────────


def test_list_projects_empty():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.projects.projects_repo.list_for_user", AsyncMock(return_value=[])):
        client = TestClient(app)
        r = client.get("/projects", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_create_project():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    project_id = uuid4()
    now = datetime.now(UTC)
    fake = MagicMock()
    fake.id = project_id
    fake.title = "Learning English"
    fake.description = "Daily vocab"
    fake.kind = "language"
    fake.target_language = "en"
    fake.native_language = None
    fake.level = "level1"
    fake.archived = False
    fake.created_at = now
    fake.updated_at = now

    with (
        patch("app.routers.projects.projects_repo.create", AsyncMock(return_value=fake)),
        patch(
            "app.routers.projects.projects_repo.find_language_by_target",
            AsyncMock(return_value=None),
        ),
    ):
        client = TestClient(app)
        r = client.post(
            "/projects",
            headers={"Authorization": "Bearer tok"},
            json={"title": "Learning English", "kind": "vocabulary"},
        )
    assert r.status_code == 201
    assert r.json()["title"] == "Learning English"
    assert r.json()["kind"] == "language"


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
        "app.routers.search.search_repo.search_conversations",
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
        "app.routers.search.search_repo.search_conversations",
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
        "app.routers.search.search_repo.search_conversations",
        AsyncMock(return_value=(fake_results, 42)),  # total=42, but only 5 returned
    ):
        client = TestClient(app)
        r = client.get(
            "/search?q=x&limit=5",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 42  # real total, not limited
    assert len(data["results"]) == 5


# ── suggestions router ──────────────────────────────────────────────────────


def test_list_suggestions_empty():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.routers.suggestions.suggestions_repo.list_active",
        AsyncMock(return_value=[]),
    ):
        client = TestClient(app)
        r = client.get("/suggestions", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_list_suggestions_returns_active():
    from fastapi.testclient import TestClient

    sid = uuid4()
    now = datetime.now(UTC)
    sug_mock = MagicMock()
    sug_mock.id = sid
    sug_mock.text = "Try writing a poem"
    sug_mock.category = "general"
    sug_mock.source = "model"
    sug_mock.created_at = now

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.routers.suggestions.suggestions_repo.list_active",
        AsyncMock(return_value=[sug_mock]),
    ):
        client = TestClient(app)
        r = client.get("/suggestions", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["text"] == "Try writing a poem"


def test_dismiss_suggestion():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with (
        patch(
            "app.routers.suggestions.suggestions_repo.dismiss",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.routers.suggestions.home_service.invalidate_home_cache",
            AsyncMock(),
        ) as invalidate_mock,
    ):
        client = TestClient(app)
        r = client.post(
            f"/suggestions/{uuid4()}/dismiss",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 204
    invalidate_mock.assert_awaited_once_with(user.id)


def test_dismiss_suggestion_not_found():
    from fastapi.testclient import TestClient

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.routers.suggestions.suggestions_repo.dismiss",
        AsyncMock(return_value=False),
    ):
        client = TestClient(app)
        r = client.post(
            f"/suggestions/{uuid4()}/dismiss",
            headers={"Authorization": "Bearer tok"},
        )
    assert r.status_code == 404


# ── suggestion generation (background job) ──────────────────────────────────


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _suggestion_sessions(*, count: int = 1) -> tuple[AsyncMock, list[_FakeSessionCM]]:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session, [_FakeSessionCM(session) for _ in range(count)]


@pytest.mark.asyncio
async def test_generate_suggestions_creates_items():
    from app.background.suggestion_generation import generate_suggestions

    uid = uuid4()
    user_mock = MagicMock()
    user_mock.id = uid
    user_mock.memory_enabled = True

    fake_items = [
        SuggestionItem(text="Suggestion 1", category="general"),
        SuggestionItem(text="Suggestion 2", category="coding"),
    ]
    structured_result = SuggestionGenerationResult(items=fake_items)

    settings = Settings()
    _, session_locals = _suggestion_sessions(count=2)

    with (
        patch(
            "app.background.suggestion_generation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.suggestion_generation.users_repo.get_by_id",
            AsyncMock(return_value=user_mock),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.delete_expired",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.count_active",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.background.suggestion_generation.chats_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.suggestion_generation.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.background.suggestion_generation.litellm_gateway.complete_structured",
            AsyncMock(return_value=structured_result),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.create_many",
            AsyncMock(),
        ) as create_many,
    ):
        await generate_suggestions(settings, uid)

    create_many.assert_awaited_once()
    # Should create 2 items.
    call_args = create_many.call_args
    assert call_args.args[1] == uid
    assert len(call_args.args[2]) == 2


@pytest.mark.asyncio
async def test_generate_suggestions_skips_when_at_cap():
    from app.background.suggestion_generation import (
        MAX_ACTIVE_SUGGESTIONS,
        generate_suggestions,
    )

    uid = uuid4()
    user_mock = MagicMock()

    settings = Settings()
    _, session_locals = _suggestion_sessions()

    with (
        patch(
            "app.background.suggestion_generation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.suggestion_generation.users_repo.get_by_id",
            AsyncMock(return_value=user_mock),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.delete_expired",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.count_active",
            AsyncMock(return_value=MAX_ACTIVE_SUGGESTIONS),  # at cap
        ),
        patch(
            "app.background.suggestion_generation.litellm_gateway.complete_structured",
            AsyncMock(),
        ) as llm_call,
        patch(
            "app.background.suggestion_generation.suggestions_repo.create_many",
            AsyncMock(),
        ) as create_many,
    ):
        await generate_suggestions(settings, uid)

    # Should skip without calling the LLM or creating.
    llm_call.assert_not_awaited()
    create_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_suggestions_user_not_found():
    from app.background.suggestion_generation import generate_suggestions

    settings = Settings()
    uid = uuid4()
    _, session_locals = _suggestion_sessions()

    with (
        patch(
            "app.background.suggestion_generation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.suggestion_generation.users_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        await generate_suggestions(settings, uid)
    # Should return early without error.


@pytest.mark.asyncio
async def test_generate_suggestions_handles_exceptions():
    from app.background.suggestion_generation import generate_suggestions

    settings = Settings()
    uid = uuid4()
    _, session_locals = _suggestion_sessions()

    with (
        patch(
            "app.background.suggestion_generation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.suggestion_generation.users_repo.get_by_id",
            AsyncMock(side_effect=RuntimeError("DB down")),
        ),
    ):
        await generate_suggestions(settings, uid)
    # Should not raise — exceptions are caught and logged.


@pytest.mark.asyncio
async def test_generate_suggestions_releases_db_before_llm():
    from app.background.suggestion_generation import generate_suggestions

    uid = uuid4()
    user_mock = MagicMock()
    user_mock.memory_enabled = True
    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_llm: list[bool] = []

    class _TrackingSessionCM(_FakeSessionCM):
        def __init__(self) -> None:
            super().__init__(session)
            self.open = False

        async def __aenter__(self) -> AsyncMock:
            self.open = True
            return await super().__aenter__()

        async def __aexit__(self, *args: object) -> None:
            self.open = False
            await super().__aexit__(*args)

    load_cm = _TrackingSessionCM()
    apply_cm = _TrackingSessionCM()

    async def fake_complete(*_args: object, **_kwargs: object) -> None:
        db_open_during_llm.append(load_cm.open or apply_cm.open)
        return None

    with (
        patch(
            "app.background.suggestion_generation.SessionLocal",
            side_effect=[load_cm, apply_cm],
        ),
        patch(
            "app.background.suggestion_generation.users_repo.get_by_id",
            AsyncMock(return_value=user_mock),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.delete_expired",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.background.suggestion_generation.suggestions_repo.count_active",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.background.suggestion_generation.chats_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.suggestion_generation.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.background.suggestion_generation.litellm_gateway.complete_structured",
            AsyncMock(side_effect=fake_complete),
        ),
    ):
        await generate_suggestions(Settings(), uid)

    assert db_open_during_llm == [False]
    assert session.commit.await_count == 1


# ── suggestions repository ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_suggestions_repo_count_active():
    from app.repositories.suggestions import count_active

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 3
    session.execute = AsyncMock(return_value=mock_result)

    count = await count_active(session, uuid4())
    assert count == 3


@pytest.mark.asyncio
async def test_suggestions_repo_list_active():
    from app.repositories.suggestions import list_active

    s = MagicMock()
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [s]
    session.execute = AsyncMock(return_value=mock_result)

    items = await list_active(session, uuid4())
    assert len(items) == 1


@pytest.mark.asyncio
async def test_suggestions_repo_dismiss_found():
    from app.models.orm import Suggestion
    from app.repositories.suggestions import dismiss

    sid = uuid4()
    uid = uuid4()
    item = MagicMock(spec=Suggestion)
    item.user_id = uid

    session = AsyncMock()
    session.get = AsyncMock(return_value=item)
    session.commit = AsyncMock()

    ok = await dismiss(session, sid, uid)
    assert ok is True
    assert item.dismissed is True


@pytest.mark.asyncio
async def test_suggestions_repo_dismiss_wrong_user():
    from app.models.orm import Suggestion
    from app.repositories.suggestions import dismiss

    sid = uuid4()
    item = MagicMock(spec=Suggestion)
    item.user_id = uuid4()  # different user

    session = AsyncMock()
    session.get = AsyncMock(return_value=item)

    ok = await dismiss(session, sid, uuid4())
    assert ok is False


@pytest.mark.asyncio
async def test_suggestions_repo_dismiss_not_found():
    from app.repositories.suggestions import dismiss

    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    ok = await dismiss(session, uuid4(), uuid4())
    assert ok is False


@pytest.mark.asyncio
async def test_suggestions_repo_create_many():
    from app.repositories.suggestions import create_many

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    await create_many(
        session,
        uuid4(),
        [
            {"text": "S1", "category": "general", "source": "model"},
            {"text": "S2", "category": "coding", "source": "model"},
        ],
    )
    assert session.add.call_count == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_suggestions_repo_delete_expired():
    from app.repositories.suggestions import delete_expired

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    deleted = await delete_expired(session)
    assert deleted == 5
    session.commit.assert_awaited_once()


# ── search repository snippet ───────────────────────────────────────────────


def test_search_snippet_exact_match():
    from app.repositories.search import _snippet

    content = "The quick brown fox jumps over the lazy dog"
    result = _snippet(content, "fox", 120)
    assert "fox" in result


def test_search_snippet_no_match():
    from app.repositories.search import _snippet

    content = "Hello world"
    result = _snippet(content, "zzz", 120)
    assert len(result) <= 120


def test_search_snippet_truncation():
    from app.repositories.search import _snippet

    content = "a" * 300 + "needle" + "b" * 300
    result = _snippet(content, "needle", 120)
    assert "needle" in result
    # Expect at most: 40 (prefix) + len(query) + 80 (suffix) + 2 (… markers) ≈ 128
    assert len(result) <= 130


# ── todos repository ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_todos_repo_create():
    from app.repositories.todos import create

    todo_mock = MagicMock()
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with (
        patch("app.repositories.todos.next_sort_order", AsyncMock(return_value=1)),
        patch("app.repositories.todos.TodoItem", return_value=todo_mock),
    ):
        result = await create(session, user_id=uuid4(), content="Task 1")
    assert result is todo_mock
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_todos_repo_update_unchecks():
    from app.repositories.todos import update

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
    from app.repositories.todos import delete_by_id

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)

    result = await delete_by_id(session, uuid4(), uuid4())
    assert result is False


# ── jobs: suggestions handler ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_suggestions_delegates():
    from app.core import jobs

    uid = uuid4()
    settings = Settings()

    with patch(
        "app.core.jobs.suggestion_generation.generate_suggestions",
        AsyncMock(),
    ) as handler:
        await jobs._handle_suggestions(settings, {"user_id": str(uid)})

    handler.assert_awaited_once()
    call_args = handler.call_args
    assert call_args.args[0] is settings
    assert call_args.args[1] == uid
