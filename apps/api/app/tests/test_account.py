"""Tests for account deletion + data export."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _fake_user():
    u = MagicMock()
    u.id = uuid4()
    u.email = "t@recall.local"
    u.name = "Tester"
    u.created_at = datetime(2024, 1, 1)
    return u


def _app_with_user(user):
    from app.core.deps import get_current_user, get_settings_dep

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings()
    return app


def test_delete_account_returns_204():
    user = _fake_user()
    app = _app_with_user(user)
    order: list[str] = []

    async def purge_sessions(*_a, **_k):
        order.append("purge_sessions")

    async def revoke(*_a, **_k):
        order.append("revoke")

    async def purge(*_a, **_k):
        order.append("purge")

    async def delete_user(*_a, **_k):
        order.append("delete_user")

    with (
        patch(
            "app.routers.auth.tokens_service.purge_user_sessions",
            side_effect=purge_sessions,
        ),
        patch(
            "app.routers.auth.google_integrations_service.revoke_all_google_tokens_for_user",
            side_effect=revoke,
        ),
        patch(
            "app.routers.auth.attachment_lifecycle.purge_attachments_for_user",
            side_effect=purge,
        ),
        patch("app.routers.auth.users_repo.delete_user", side_effect=delete_user),
    ):
        client = TestClient(app)
        r = client.delete("/auth/me", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 204
    # Sessions must be purged first — otherwise a logged-in client keeps a
    # working access token after the row is gone, with only the (now-deleted)
    # DB user check to stop it.
    assert order == ["purge_sessions", "revoke", "purge", "delete_user"]


def test_export_returns_data():
    user = _fake_user()
    app = _app_with_user(user)

    async def fake_iter(_user):
        yield '{"exported_at":"now","export_limits":{},"user":{},"chats":[],"memories":[]}'

    with patch("app.routers.auth.export_service.iter_export_json", fake_iter):
        client = TestClient(app)
        r = client.get("/auth/me/export", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json()["exported_at"] == "now"


@pytest.mark.asyncio
async def test_delete_user_deletes_children_then_user():
    from app.repositories import users as users_repo

    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock())
    await users_repo.delete_user(session, uuid4())
    # Every user-owned table is purged before the user row itself, so the delete
    # never fails on an FK to users.id without ON DELETE CASCADE. 13 tables are
    # cleared explicitly (messages, memories, usage, project_items, projects,
    # todos, suggestions, suggested_reminders, push_tokens,
    # attachments, calendar connections, gmail connections, chats).
    assert session.execute.await_count == 13
    session.delete.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_export_structure():
    from app.services import export_service

    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.email = "e@x"
    user.name = "n"
    user.created_at = datetime(2024, 1, 1)

    chat = MagicMock()
    chat.id = uuid4()
    chat.title = "T"
    chat.model = "free-chat"
    chat.pinned = False
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    msg = MagicMock(role="user", content="hi", model=None, created_at=datetime(2024, 1, 1))
    mem = MagicMock(type="fact", text="x", confidence=None, created_at=datetime(2024, 1, 1))

    todo = MagicMock()
    todo.id = uuid4()
    todo.content = "buy milk"
    todo.topic = "General"
    todo.checked = False
    todo.due_at = None
    todo.chat_id = None
    todo.project_id = None
    todo.sort_order = 1
    todo.created_at = datetime(2024, 1, 1)
    todo.updated_at = datetime(2024, 1, 1)

    project = MagicMock()
    project.id = uuid4()
    project.title = "Spanish"
    project.description = None
    project.kind = "language"
    project.target_language = "es"
    project.native_language = "en"
    project.level = "level1"
    project.daily_goal = 5
    project.archived = False
    project.created_at = datetime(2024, 1, 1)
    project.updated_at = datetime(2024, 1, 1)

    item = MagicMock()
    item.id = uuid4()
    item.project_id = project.id
    item.list_title = "General"
    item.content = "hola"
    item.note = None
    item.definition = "hello"
    item.example_sentence = None
    item.status = "new"
    item.mastered = False
    item.mastered_at = None
    item.review_count = 0
    item.quiz_attempts = 0
    item.quiz_correct = 0
    item.created_at = datetime(2024, 1, 1)
    item.updated_at = datetime(2024, 1, 1)

    with (
        patch(
            "app.services.export_service.chats_repo.list_for_user",
            AsyncMock(return_value=[chat]),
        ),
        patch(
            "app.services.export_service.messages_repo.list_range",
            AsyncMock(return_value=[msg]),
        ),
        patch(
            "app.services.export_service.memories_repo.list_range",
            AsyncMock(return_value=[mem]),
        ),
        patch(
            "app.services.export_service.todos_repo.list_for_user",
            AsyncMock(return_value=[todo]),
        ),
        patch(
            "app.services.export_service.projects_repo.list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch(
            "app.services.export_service.project_items_repo.list_for_projects",
            AsyncMock(return_value=[item]),
        ),
    ):
        data = await export_service.build_export(session, user)

    assert data["user"]["email"] == "e@x"
    assert len(data["chats"]) == 1
    assert data["chats"][0]["messages"][0]["content"] == "hi"
    assert len(data["memories"]) == 1
    assert data["todos"][0]["content"] == "buy milk"
    assert data["projects"][0]["title"] == "Spanish"
    assert data["projects"][0]["items"][0]["content"] == "hola"
    assert data["export_limits"]["max_chats"] == export_service.EXPORT_MAX_CHATS
    assert (
        data["export_limits"]["max_messages_per_chat"]
        == export_service.EXPORT_MAX_MESSAGES_PER_CHAT
    )
    assert data["export_limits"]["max_todos"] == export_service.EXPORT_MAX_TODOS
    assert data["export_limits"]["max_projects"] == export_service.EXPORT_MAX_PROJECTS


@pytest.mark.asyncio
async def test_build_export_pages_messages_per_chat():
    from app.services import export_service

    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.email = "e@x"
    user.name = "n"
    user.created_at = datetime(2024, 1, 1)

    chat = MagicMock()
    chat.id = uuid4()
    chat.title = "T"
    chat.model = "free-chat"
    chat.pinned = False
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    page_one = [
        MagicMock(role="user", content="one", model=None, created_at=datetime(2024, 1, 1)),
        MagicMock(
            role="assistant", content="two", model="free-chat", created_at=datetime(2024, 1, 2)
        ),
    ]
    page_two = [
        MagicMock(role="user", content="three", model=None, created_at=datetime(2024, 1, 3)),
    ]

    async def list_range(_session, _chat_id, *, offset, limit):
        if offset == 0:
            return page_one
        if offset == len(page_one):
            return page_two
        return []

    with (
        patch.object(export_service, "EXPORT_MESSAGE_PAGE_SIZE", 2),
        patch(
            "app.services.export_service.chats_repo.list_for_user",
            AsyncMock(return_value=[chat]),
        ),
        patch(
            "app.services.export_service.messages_repo.list_range",
            AsyncMock(side_effect=list_range),
        ),
        patch(
            "app.services.export_service.memories_repo.list_range",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.export_service.todos_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.export_service.projects_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
    ):
        data = await export_service.build_export(session, user)

    contents = [message["content"] for message in data["chats"][0]["messages"]]
    assert contents == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_build_export_pages_memories():
    from app.services import export_service

    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.email = "e@x"
    user.name = "n"
    user.created_at = datetime(2024, 1, 1)

    mem_one = MagicMock(type="fact", text="a", confidence=0.9, created_at=datetime(2024, 1, 1))
    mem_two = MagicMock(type="focus", text="b", confidence=0.8, created_at=datetime(2024, 1, 2))
    mem_three = MagicMock(
        type="profile", text="c", confidence=None, created_at=datetime(2024, 1, 3)
    )

    async def list_memories(_session, _user_id, *, offset, limit):
        page = [mem_one, mem_two, mem_three]
        return page[offset : offset + limit]

    with (
        patch.object(export_service, "EXPORT_MEMORY_PAGE_SIZE", 2),
        patch(
            "app.services.export_service.chats_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.export_service.memories_repo.list_range",
            AsyncMock(side_effect=list_memories),
        ),
        patch(
            "app.services.export_service.todos_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.export_service.projects_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
    ):
        data = await export_service.build_export(session, user)

    assert [memory["text"] for memory in data["memories"]] == ["a", "b", "c"]
