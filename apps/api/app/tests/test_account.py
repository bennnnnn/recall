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
    with (
        patch(
            "app.routers.auth.google_integrations_service.revoke_all_google_tokens_for_user",
            AsyncMock(),
        ) as revoke_mock,
        patch("app.routers.auth.users_repo.delete_user", AsyncMock()) as deleter,
    ):
        client = TestClient(app)
        r = client.delete("/auth/me", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 204
    revoke_mock.assert_awaited_once()
    deleter.assert_awaited_once()


def test_export_returns_data():
    user = _fake_user()
    app = _app_with_user(user)
    payload = {"exported_at": "now", "user": {}, "chats": [], "memories": []}
    with patch("app.routers.auth.export_service.build_export", AsyncMock(return_value=payload)):
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

    with (
        patch(
            "app.services.export_service.chats_repo.list_for_user",
            AsyncMock(return_value=[chat]),
        ),
        patch("app.services.export_service.messages_repo.list_all", AsyncMock(return_value=[msg])),
        patch(
            "app.services.export_service.memories_repo.list_for_user",
            AsyncMock(return_value=[mem]),
        ),
    ):
        data = await export_service.build_export(session, user)

    assert data["user"]["email"] == "e@x"
    assert len(data["chats"]) == 1
    assert data["chats"][0]["messages"][0]["content"] == "hi"
    assert len(data["memories"]) == 1
    assert data["export_limits"]["max_chats"] == export_service.EXPORT_MAX_CHATS
    assert (
        data["export_limits"]["max_messages_per_chat"]
        == export_service.EXPORT_MAX_MESSAGES_PER_CHAT
    )
