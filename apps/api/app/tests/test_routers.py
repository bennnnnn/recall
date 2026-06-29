"""Router-level tests using FastAPI TestClient with mocked dependencies."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.orm import User


def _fake_user(**kw) -> User:
    u = MagicMock(spec=User)
    u.id = kw.get("id", uuid4())
    u.email = kw.get("email", "test@recall.local")
    u.name = kw.get("name", "Tester")
    u.avatar_url = None
    u.default_model = "auto"
    u.plan = kw.get("plan", "free")
    u.enabled_models = kw.get("enabled_models", None)
    u.response_style = "balanced"
    u.response_tone = kw.get("response_tone", "funny")
    u.memory_enabled = True
    u.locale = kw.get("locale", "en")
    u.timezone = kw.get("timezone", "UTC")
    u.location = kw.get("location", None)
    u.created_at = datetime(2024, 1, 1)
    return u


def _app_with_user(user: User):
    """Create a test app with a fixed current_user dependency."""
    from app.core.deps import get_current_user, get_settings_dep

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings()
    return app


# ── health ─────────────────────────────────────────────────────────────────────


def test_health():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── auth /me ───────────────────────────────────────────────────────────────────


def test_me_returns_user():
    user = _fake_user()
    client = TestClient(_app_with_user(user))
    r = client.get("/auth/me", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json()["email"] == user.email


def test_me_patch_updates_user():
    user = _fake_user()
    app = _app_with_user(user)

    with patch(
        "app.routers.auth.users_repo.update",
        AsyncMock(return_value=user),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"response_style": "short"},
        )
    assert r.status_code == 200


# ── dev login ──────────────────────────────────────────────────────────────────


def test_dev_login():
    from app.models.schemas import AuthResponse, UserOut

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="dev@recall.local",
        name="Dev",
        avatar_url=None,
        default_model="auto",
        plan="free",
        enabled_models=None,
        response_style="balanced",
        memory_enabled=True,
        created_at=datetime(2024, 1, 1),
    )
    fake_resp = AuthResponse(access_token="fake-token", user=fake_user_out)

    app = create_app()
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True, jwt_secret="test-secret-32-chars-long-enough!!"
    )

    with patch("app.routers.auth.auth_service.login_dev", AsyncMock(return_value=fake_resp)):
        client = TestClient(app)
        r = client.post(
            "/auth/dev",
            json={"email": "dev@recall.local", "name": "Dev"},
        )
    assert r.status_code == 200
    assert r.json()["access_token"] == "fake-token"


def test_dev_login_disabled_returns_403():
    app = create_app()
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(dev_auth_enabled=False)
    client = TestClient(app)
    r = client.post("/auth/dev", json={"email": "x@x.com", "name": "X"})
    assert r.status_code == 403


# ── chats ──────────────────────────────────────────────────────────────────────


def test_create_chat():
    from app.models.orm import Chat

    user = _fake_user()
    chat = MagicMock(spec=Chat)
    chat.id = uuid4()
    chat.title = None
    chat.model = "free-chat"
    chat.pinned = False
    chat.project_id = None
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    app = _app_with_user(user)
    with patch("app.routers.chats.chats_repo.create", AsyncMock(return_value=chat)):
        client = TestClient(app)
        r = client.post(
            "/chats", headers={"Authorization": "Bearer tok"}, json={"model": "free-chat"}
        )
    assert r.status_code == 201
    assert r.json()["model"] == "free-chat"


def test_list_chats():
    user = _fake_user()
    app = _app_with_user(user)
    empty_list: list = []

    with (
        patch("app.routers.chats.chats_repo.list_for_user", AsyncMock(return_value=empty_list)),
        patch(
            "app.routers.chats.chats_repo.list_archived_for_user",
            AsyncMock(return_value=empty_list),
        ),
        patch(
            "app.routers.chats.chats_repo.group_by_recency",
            return_value={"today": [], "yesterday": [], "earlier": []},
        ),
    ):
        client = TestClient(app)
        r = client.get("/chats", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == {"pinned": [], "today": [], "yesterday": [], "earlier": [], "archived": []}


def test_get_chat_not_found():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.chats.chats_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.get(f"/chats/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


def test_today_usage():
    import fakeredis.aioredis

    from app.core.deps import get_redis

    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    with patch("app.routers.chats.usage_repo.get_for_date", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.get("/chats/usage/today", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    assert "remaining" in data
    assert data["remaining"] == data["daily_limit"]


# ── memories ───────────────────────────────────────────────────────────────────


def test_list_memories_empty():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.memories.memories_repo.list_for_user", AsyncMock(return_value=[])):
        client = TestClient(app)
        r = client.get("/memories", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_delete_memory_not_found():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.memories.memory_service.delete_memory", AsyncMock(return_value=False)):
        client = TestClient(app)
        r = client.delete(f"/memories/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


def test_delete_memory_ok():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.memories.memory_service.delete_memory", AsyncMock(return_value=True)):
        client = TestClient(app)
        r = client.delete(f"/memories/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 204
