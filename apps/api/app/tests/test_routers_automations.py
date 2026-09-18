"""Automations router tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_settings_dep
from app.main import create_app
from app.models.orm import User


def _fake_user(*, plan: str = "pro") -> User:
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@recall.local"
    user.plan = plan
    user.timezone = "UTC"
    return user


def _app_with_user(user: User, *, settings: Settings | None = None):
    from app.core.deps import get_current_user

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings or Settings(
        automations_enabled=True
    )

    async def _get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _get_db
    return app


def _automation_out(**overrides) -> MagicMock:
    automation = MagicMock()
    automation.id = overrides.get("id", uuid4())
    automation.chat_id = overrides.get("chat_id", uuid4())
    automation.prompt = overrides.get("prompt", "Find L3 backend jobs")
    automation.frequency = overrides.get("frequency", "daily")
    automation.next_run_at = overrides.get("next_run_at", datetime.now(UTC))
    automation.status = overrides.get("status", "active")
    automation.last_run_at = overrides.get("last_run_at", None)
    automation.last_run_status = overrides.get("last_run_status", None)
    automation.created_at = datetime.now(UTC)
    automation.updated_at = datetime.now(UTC)
    return automation


def test_list_automations_returns_items():
    user = _fake_user()
    app = _app_with_user(user)
    item = _automation_out()
    with patch(
        "app.services.automations.crud.automations_repo.list_for_user",
        AsyncMock(return_value=[item]),
    ):
        client = TestClient(app)
        r = client.get("/automations", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["prompt"] == "Find L3 backend jobs"


def test_list_automations_404s_when_feature_disabled():
    user = _fake_user()
    app = _app_with_user(user, settings=Settings(automations_enabled=False))
    client = TestClient(app)
    r = client.get("/automations", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


def test_create_automation_requires_pro():
    user = _fake_user(plan="free")
    app = _app_with_user(user)
    client = TestClient(app)
    r = client.post(
        "/automations",
        headers={"Authorization": "Bearer tok"},
        json={
            "prompt": "Find L3 backend jobs",
            "frequency": "daily",
            "next_run_at": "2026-09-18T08:00:00Z",
        },
    )
    assert r.status_code == 403


def test_create_automation_success():
    user = _fake_user()
    app = _app_with_user(user)
    created = _automation_out()
    chat = MagicMock()
    chat.id = created.chat_id

    with (
        patch(
            "app.services.automations.crud.automations_repo.count_active_for_user",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.services.automations.crud.chats_repo.create",
            AsyncMock(return_value=chat),
        ),
        patch(
            "app.services.automations.crud.automations_repo.create",
            AsyncMock(return_value=created),
        ),
    ):
        client = TestClient(app)
        r = client.post(
            "/automations",
            headers={"Authorization": "Bearer tok"},
            json={
                "prompt": "Find L3 backend jobs",
                "frequency": "daily",
                "next_run_at": "2026-09-18T08:00:00Z",
            },
        )
    assert r.status_code == 201
    assert r.json()["prompt"] == "Find L3 backend jobs"


def test_create_automation_active_cap_returns_422():
    user = _fake_user()
    app = _app_with_user(
        user, settings=Settings(automations_enabled=True, automations_max_active_per_user=1)
    )
    with patch(
        "app.services.automations.crud.automations_repo.count_active_for_user",
        AsyncMock(return_value=1),
    ):
        client = TestClient(app)
        r = client.post(
            "/automations",
            headers={"Authorization": "Bearer tok"},
            json={
                "prompt": "Find L3 backend jobs",
                "frequency": "daily",
                "next_run_at": "2026-09-18T08:00:00Z",
            },
        )
    assert r.status_code == 422


def test_get_automation_404s_when_missing():
    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.services.automations.crud.automations_repo.get_by_id",
        AsyncMock(return_value=None),
    ):
        client = TestClient(app)
        r = client.get(f"/automations/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


def test_update_automation_pauses():
    user = _fake_user()
    app = _app_with_user(user)
    existing = _automation_out()
    paused = _automation_out(status="paused")
    with (
        patch(
            "app.services.automations.crud.automations_repo.get_by_id",
            AsyncMock(return_value=existing),
        ),
        patch(
            "app.services.automations.crud.automations_repo.update",
            AsyncMock(return_value=paused),
        ),
    ):
        client = TestClient(app)
        r = client.patch(
            f"/automations/{existing.id}",
            headers={"Authorization": "Bearer tok"},
            json={"status": "paused"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "paused"


def test_update_automation_rejects_completed_status():
    user = _fake_user()
    app = _app_with_user(user)
    client = TestClient(app)
    r = client.patch(
        f"/automations/{uuid4()}",
        headers={"Authorization": "Bearer tok"},
        json={"status": "completed"},
    )
    assert r.status_code == 422


def test_delete_automation_deletes_the_chat():
    user = _fake_user()
    app = _app_with_user(user)
    existing = _automation_out()
    with (
        patch(
            "app.services.automations.crud.automations_repo.get_by_id",
            AsyncMock(return_value=existing),
        ),
        patch(
            "app.services.automations.crud.chats_service.delete_chat", AsyncMock()
        ) as delete_chat,
    ):
        client = TestClient(app)
        r = client.delete(f"/automations/{existing.id}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 204
    delete_chat.assert_awaited_once()


def test_delete_automation_404s_when_missing():
    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.services.automations.crud.automations_repo.get_by_id",
        AsyncMock(return_value=None),
    ):
        client = TestClient(app)
        r = client.delete(f"/automations/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404
