"""Router-level tests using FastAPI TestClient with mocked dependencies."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
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
    u.location_enabled = kw.get("location_enabled", bool(kw.get("location")))
    u.custom_instructions = kw.get("custom_instructions", None)
    u.age = kw.get("age", None)
    u.country = kw.get("country", None)
    u.job = kw.get("job", None)
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


# ── models ─────────────────────────────────────────────────────────────────────


def test_list_models_omits_provider_field():
    user = _fake_user()
    client = TestClient(_app_with_user(user))
    r = client.get("/models", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) > 0
    for model in body:
        assert "id" in model
        assert "label" in model
        assert "quota_multiplier" in model
        assert "provider" not in model
    smart = next(m for m in body if m["id"] == "smart-chat")
    assert smart["quota_multiplier"] == 3.5
    assert all(m["id"] != "max-chat" for m in body)


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
        "app.services.account_lifecycle.users_repo.update",
        AsyncMock(return_value=user),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"response_style": "short"},
        )
    assert r.status_code == 200


def test_me_patch_invalidates_memory_cache_on_toggle():
    user = _fake_user()
    user.memory_enabled = True
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(return_value=user)),
        patch(
            "app.services.account_lifecycle.memory_service.invalidate_memory_block",
            invalidate_mock,
        ),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"memory_enabled": False},
        )

    assert r.status_code == 200
    invalidate_mock.assert_awaited_once_with(user.id)


def test_me_patch_invalidates_home_cache():
    user = _fake_user()
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(return_value=user)),
        patch(
            "app.services.account_lifecycle.home_service.invalidate_home_cache",
            invalidate_mock,
        ),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"name": "New Name"},
        )

    assert r.status_code == 200
    invalidate_mock.assert_awaited_once_with(user.id)


def test_me_patch_skips_memory_invalidation_when_unchanged():
    user = _fake_user()
    user.memory_enabled = True
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(return_value=user)),
        patch(
            "app.services.account_lifecycle.memory_service.invalidate_memory_block",
            invalidate_mock,
        ),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"memory_enabled": True},
        )

    assert r.status_code == 200
    invalidate_mock.assert_not_called()


def test_me_patch_rejects_blank_name():
    user = _fake_user()
    client = TestClient(_app_with_user(user))
    r = client.patch(
        "/auth/me",
        headers={"Authorization": "Bearer tok"},
        json={"name": "   "},
    )
    assert r.status_code == 422


def test_me_patch_persists_custom_instructions_and_blank_clears():
    user = _fake_user()
    app = _app_with_user(user)
    captured: dict[str, object] = {}

    async def capture(_session, _user, **fields):
        captured.update(fields)
        return user

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(side_effect=capture)),
        # The global REST rate limiter reads the real Redis; disable it so this
        # test is deterministic regardless of local Redis state.
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"custom_instructions": "  Always answer in bullet points.  "},
        )
    assert r.status_code == 200
    assert captured["custom_instructions"] == "Always answer in bullet points."

    # An empty/whitespace value normalizes to None (clears the field).
    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(side_effect=capture)),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        r2 = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"custom_instructions": "   "},
        )
    assert r2.status_code == 200
    assert captured["custom_instructions"] is None


def test_me_patch_accepts_supported_locale_and_normalizes():
    user = _fake_user()
    app = _app_with_user(user)
    captured: dict[str, object] = {}

    async def capture(_session, _user, **fields):
        captured.update(fields)
        return user

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(side_effect=capture)),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        client = TestClient(app)
        # "es-MX" normalizes to "es" (split on -, lowercased) — a supported code.
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"locale": "es-MX"},
        )
    assert r.status_code == 200
    assert captured["locale"] == "es"


def test_me_patch_rejects_unsupported_locale():
    user = _fake_user()
    app = _app_with_user(user)

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock()) as update,
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"locale": "klingon"},
        )
    assert r.status_code == 422
    update.assert_not_awaited()
    assert "Unsupported locale" in r.text


def test_me_patch_treats_empty_locale_as_noop():
    """An empty/whitespace locale string is treated as unset (no change),
    matching the custom_instructions blank-clears behavior — not stored as ''."""
    user = _fake_user()
    app = _app_with_user(user)
    captured: dict[str, object] = {}

    async def capture(_session, _user, **fields):
        captured.update(fields)
        return user

    with (
        patch("app.services.account_lifecycle.users_repo.update", AsyncMock(side_effect=capture)),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"locale": "   "},
        )
    assert r.status_code == 200
    # locale should not be passed through to the update (treated as no-change).
    assert "locale" not in captured or captured.get("locale") is None


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
    fake_resp = AuthResponse(
        access_token="fake-token",
        refresh_token="fake-refresh",
        user=fake_user_out,
    )

    app = create_app()
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        dev_auth_allow_remote=True,
        jwt_secret="test-secret-32-chars-long-enough!!",
    )

    with (
        patch("app.routers.auth.auth_service.login_dev", AsyncMock(return_value=fake_resp)),
        patch("app.routers.auth.allow_request_fail_closed", AsyncMock(return_value=True)),
    ):
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


def test_dev_login_rate_limited_returns_429():
    """Dev login shares the per-IP rate limit pattern of Google/Apple so a
    single client can't mint arbitrary accounts or credential-stuff when dev
    auth is on."""
    app = create_app()
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True, jwt_secret="test-secret-32-chars-long-enough!!"
    )
    with (
        patch("app.routers.auth.auth_service.login_dev", AsyncMock()),
        patch("app.routers.auth.allow_request_fail_closed", AsyncMock(return_value=False)),
    ):
        client = TestClient(app)
        r = client.post("/auth/dev", json={"email": "x@x.com", "name": "X"})
    assert r.status_code == 429
    assert "Too many login attempts" in r.json()["detail"]


def test_dev_login_refuses_non_loopback_without_allow_remote():
    """A dev config accidentally exposed on a public host must not mint
    accounts for remote callers. /auth/dev returns 404 (not 403 — don't leak
    that the endpoint exists) unless DEV_AUTH_ALLOW_REMOTE is explicitly set.
    The TestClient's peer is "testclient", which is not loopback."""
    app = create_app()
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        dev_auth_allow_remote=False,
        jwt_secret="test-secret-32-chars-long-enough!!",
    )
    with (
        patch("app.routers.auth.auth_service.login_dev", AsyncMock()) as login_dev,
        patch("app.routers.auth.allow_request_fail_closed", AsyncMock(return_value=True)),
    ):
        client = TestClient(app)
        r = client.post("/auth/dev", json={"email": "x@x.com", "name": "X"})
    assert r.status_code == 404
    # Account minting must never run for a refused remote request.
    login_dev.assert_not_called()


def test_dev_login_ignores_spoofed_loopback_forwarded_ip():
    """Fly-Client-IP / XFF must not bypass the peer loopback guard."""
    app = create_app()
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        dev_auth_allow_remote=False,
        trust_x_forwarded_for=True,
        trusted_proxy_cidrs="0.0.0.0/0",
        jwt_secret="test-secret-32-chars-long-enough!!",
    )
    with (
        patch("app.routers.auth.auth_service.login_dev", AsyncMock()) as login_dev,
        patch("app.routers.auth.allow_request_fail_closed", AsyncMock(return_value=True)),
    ):
        client = TestClient(app)
        r = client.post(
            "/auth/dev",
            json={"email": "x@x.com", "name": "X"},
            headers={"Fly-Client-IP": "127.0.0.1", "X-Forwarded-For": "127.0.0.1"},
        )
    assert r.status_code == 404
    login_dev.assert_not_called()


def test_revenuecat_webhook_503_when_no_auth_and_no_dev_opt_in():
    """Webhook auth must never be skipped based on `environment` alone — a
    dev config on a public host would let anyone grant themselves Pro. With
    no shared secret and no explicit DEV_ALLOW_UNAUTHED_WEBHOOKS, return 503."""
    app = create_app()
    from app.core.deps import get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=False,
    )
    client = TestClient(app)
    r = client.post("/webhooks/revenuecat", json={"event": {"type": "TEST"}})
    assert r.status_code == 503


def test_revenuecat_webhook_rejects_oversized_body():
    from fastapi import HTTPException

    from app.routers import webhooks as webhooks_mod

    with pytest.raises(HTTPException) as exc:
        webhooks_mod._reject_oversized_webhook_body(str(200_000), 0)
    assert exc.value.status_code == 413

    app = create_app()
    from app.core.deps import get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="whsec-secret",
        dev_allow_unauthed_webhooks=False,
    )
    client = TestClient(app)
    r = client.post(
        "/webhooks/revenuecat",
        content=b"x" * (65 * 1024),
        headers={
            "Authorization": "whsec-secret",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 413


# ── chats ──────────────────────────────────────────────────────────────────────


def test_create_chat():
    from app.models.orm import Chat

    user = _fake_user()
    chat = MagicMock(spec=Chat)
    chat.id = uuid4()
    chat.title = None
    chat.model = "free-chat"
    chat.pinned = False
    chat.archived = False
    chat.quiz_mode = None
    chat.project_id = None
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    app = _app_with_user(user)
    with patch("app.services.chats.chats_repo.create", AsyncMock(return_value=chat)):
        client = TestClient(app)
        r = client.post(
            "/chats", headers={"Authorization": "Bearer tok"}, json={"model": "free-chat"}
        )
    assert r.status_code == 201
    assert r.json()["model"] == "free-chat"


def test_create_chat_with_other_users_project_id_rejected():
    from app.models.orm import Chat

    user = _fake_user()
    app = _app_with_user(user)
    chat = MagicMock(spec=Chat)
    chat.id = uuid4()
    chat.title = None
    chat.model = "free-chat"
    chat.pinned = False
    chat.archived = False
    chat.quiz_mode = None
    chat.project_id = None
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    # project_id that doesn't belong to the user → projects_repo.get_by_id
    # returns None → router must 400 instead of linking to a foreign project.
    pid = uuid4()
    with patch("app.services.chats.projects_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.post(
            "/chats",
            headers={"Authorization": "Bearer tok"},
            json={"model": "free-chat", "project_id": str(pid)},
        )
    assert r.status_code == 400
    assert "Project not found" in r.json()["detail"]


def test_create_chat_with_owned_project_id_accepted():
    from app.models.orm import Chat

    user = _fake_user()
    app = _app_with_user(user)
    pid = uuid4()
    chat = MagicMock(spec=Chat)
    chat.id = uuid4()
    chat.title = None
    chat.model = "free-chat"
    chat.pinned = False
    chat.archived = False
    chat.quiz_mode = None
    chat.project_id = pid
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    project = MagicMock()
    project.id = pid
    project.user_id = user.id
    with (
        patch("app.services.chats.projects_repo.get_by_id", AsyncMock(return_value=project)),
        patch("app.services.chats.chats_repo.create", AsyncMock(return_value=chat)),
    ):
        client = TestClient(app)
        r = client.post(
            "/chats",
            headers={"Authorization": "Bearer tok"},
            json={"model": "free-chat", "project_id": str(pid)},
        )
    assert r.status_code == 201


def test_list_chats():
    user = _fake_user()
    app = _app_with_user(user)
    empty_list: list = []

    with (
        patch("app.services.chats.chats_repo.list_for_user", AsyncMock(return_value=empty_list)),
        patch(
            "app.services.chats.chats_repo.list_archived_for_user",
            AsyncMock(return_value=empty_list),
        ),
        patch(
            "app.services.chats.chats_repo.group_by_recency",
            return_value={
                "today": [],
                "yesterday": [],
                "last_7_days": [],
                "this_month": [],
                "older": [],
            },
        ),
    ):
        client = TestClient(app)
        r = client.get("/chats", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == {
        "pinned": [],
        "today": [],
        "yesterday": [],
        "last_7_days": [],
        "this_month": [],
        "older": [],
        "archived": [],
    }


def test_list_chats_never_overlaps_ops_on_one_session():
    """The active + archived queries run concurrently, and an AsyncSession can
    only run one operation at a time (asyncpg raises InterfaceError on
    overlap) — so each concurrent query must get its own session. Simulate
    asyncpg's guard: mark a session busy across a yield point and record a
    violation if a second operation lands on it while busy."""
    import asyncio

    user = _fake_user()
    app = _app_with_user(user)
    busy: set[int] = set()
    violations: list[str] = []

    def tracked(name: str, result: list):
        async def impl(s, *args, **kwargs):
            sid = id(s)
            if sid in busy:
                violations.append(name)
            busy.add(sid)
            await asyncio.sleep(0)  # yield so gathered queries interleave
            busy.discard(sid)
            return result

        return impl

    with (
        patch(
            "app.services.chats.chats_repo.list_for_user",
            AsyncMock(side_effect=tracked("active", [])),
        ),
        patch(
            "app.services.chats.chats_repo.list_archived_for_user",
            AsyncMock(side_effect=tracked("archived", [])),
        ),
        patch(
            "app.services.chats.chats_repo.group_by_recency",
            return_value={
                "today": [],
                "yesterday": [],
                "last_7_days": [],
                "this_month": [],
                "older": [],
            },
        ),
    ):
        client = TestClient(app)
        r = client.get("/chats", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 200
    assert violations == []


def test_get_chat_not_found():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.services.chats.chats_repo.get_by_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.get(f"/chats/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


def test_list_messages_enqueues_topic_backfill():
    import fakeredis.aioredis

    from app.core.deps import get_redis
    from app.models.orm import Chat, Message

    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    chat_id = uuid4()
    chat = MagicMock(spec=Chat)
    chat.id = chat_id
    chat.title = None

    user_msg = MagicMock(spec=Message)
    user_msg.role = "user"
    user_msg.content = "Explain Rust ownership"
    user_msg.id = uuid4()
    user_msg.model = "free-chat"
    user_msg.feedback = None
    user_msg.recalled = False
    user_msg.memory_hints = None
    user_msg.context_summarized = None
    user_msg.search_sources = None
    user_msg.created_at = datetime(2024, 1, 1)

    asst_msg = MagicMock(spec=Message)
    asst_msg.role = "assistant"
    asst_msg.content = "Rust ownership prevents data races."
    asst_msg.id = uuid4()
    asst_msg.model = "free-chat"
    asst_msg.feedback = None
    asst_msg.recalled = False
    asst_msg.memory_hints = None
    asst_msg.context_summarized = None
    asst_msg.search_sources = None
    asst_msg.created_at = datetime(2024, 1, 1)

    with (
        patch("app.services.chats.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.services.chats.messages_repo.list_page",
            AsyncMock(return_value=([user_msg, asst_msg], False)),
        ),
        patch("app.services.chats.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        client = TestClient(app)
        r = client.get(f"/chats/{chat_id}/messages", headers={"Authorization": "Bearer tok"})
        r2 = client.get(f"/chats/{chat_id}/messages", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 200
    assert r2.status_code == 200
    enqueue_job.assert_awaited_once()
    assert enqueue_job.call_args.args[1] == "topic"
    payload = enqueue_job.call_args.args[2]
    assert payload["user_message"] == user_msg.content
    assert payload["assistant_message"] == asst_msg.content


def test_rename_chat_rejects_blank_title():
    user = _fake_user()
    app = _app_with_user(user)
    chat_id = uuid4()
    chat = MagicMock()
    chat.id = chat_id

    with patch("app.services.chats.chats_repo.get_by_id", AsyncMock(return_value=chat)):
        client = TestClient(app)
        r = client.patch(
            f"/chats/{chat_id}",
            headers={"Authorization": "Bearer tok"},
            json={"title": '   "'},
        )
    assert r.status_code == 400


def test_today_usage():
    import fakeredis.aioredis

    from app.core.deps import get_redis

    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    with patch("app.services.chats.usage_repo.get_for_date", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.get("/chats/usage/today", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    assert "remaining" in data
    assert "used_tokens" in data
    assert data["remaining"] == data["daily_limit"] - data["used_tokens"]
    assert data["context_token_budget"] == 6000
    assert data["recent_message_window"] == 20


def test_today_usage_falls_back_to_db_total_when_redis_flushed():
    """After a Redis flush, the usage display must not reset to zero — it
    reconciles against the DB-recorded total so users see real consumption."""
    import fakeredis.aioredis

    from app.core.deps import get_redis

    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    db_usage = MagicMock()
    db_usage.input_tokens = 8_000
    db_usage.output_tokens = 4_000

    with patch("app.services.chats.usage_repo.get_for_date", AsyncMock(return_value=db_usage)):
        client = TestClient(app)
        r = client.get("/chats/usage/today", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    # Redis is empty (0); DB total (12_000) wins via the max() reconciliation.
    assert data["used_tokens"] == 12_000
    assert data["input_tokens"] == 8_000
    assert data["output_tokens"] == 4_000
    assert data["remaining"] == data["daily_limit"] - 12_000


# ── memories ───────────────────────────────────────────────────────────────────


def test_list_memories_empty():
    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.services.memory.enqueue_policy.memories_repo.list_for_user",
        AsyncMock(return_value=[]),
    ):
        client = TestClient(app)
        r = client.get("/memories", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_consolidate_memories_skipped_when_memory_disabled():
    user = _fake_user()
    user.memory_enabled = False
    app = _app_with_user(user)
    with patch(
        "app.services.memory.enqueue_policy.memories_repo.list_for_user",
        AsyncMock(),
    ) as list_mock:
        client = TestClient(app)
        r = client.post("/memories/consolidate", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 202
    assert r.json() == {"status": "skipped"}
    list_mock.assert_not_awaited()


def test_list_memories_skips_consolidation_scan_when_already_locked():
    """BUG FIX (perf): GET /memories runs on every plain list load. Once a
    consolidation job is already queued/locked for this user, a repeat load
    must not re-run sections_need_consolidation's text scan over every
    memory section — it should short-circuit on the cheap lock check."""
    import fakeredis.aioredis

    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    def _messy_memory() -> MagicMock:
        m = MagicMock()
        m.id = uuid4()
        m.type = "profile"
        m.text = "User's name is Bini. User's name is Binalfew. User is a developer."
        m.confidence = 0.9
        m.created_at = datetime(2024, 1, 1)
        m.updated_at = datetime(2024, 1, 1)
        return m

    with (
        patch("app.routers.memories.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.memory.enqueue_policy.memories_repo.list_for_user",
            AsyncMock(side_effect=lambda *a, **kw: [_messy_memory()]),
        ),
        patch("app.services.memory.enqueue_policy.jobs.enqueue", AsyncMock()) as enqueue_job,
        patch(
            "app.services.memory.enqueue_policy.memory_service.sections_need_consolidation",
            wraps=lambda sections: True,
        ) as scan_mock,
    ):
        client = TestClient(app)
        r1 = client.get("/memories", headers={"Authorization": "Bearer tok"})
        r2 = client.get("/memories", headers={"Authorization": "Bearer tok"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second load found the lock already held and skipped the scan entirely.
    scan_mock.assert_called_once()
    enqueue_job.assert_awaited_once()


def test_delete_memory_not_found():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.memories.memory_service.delete_memory", AsyncMock(return_value=False)):
        client = TestClient(app)
        r = client.delete(f"/memories/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 404


def test_update_memory_ok():
    user = _fake_user()
    app = _app_with_user(user)
    memory_id = uuid4()
    updated = MagicMock()
    updated.id = memory_id
    updated.type = "fact"
    updated.text = "As of 2026-07-20: Likes hiking"
    updated.confidence = 0.9
    updated.created_at = datetime(2026, 1, 1)
    updated.updated_at = datetime(2026, 7, 20)
    with patch(
        "app.routers.memories.memory_service.update_memory",
        AsyncMock(return_value=updated),
    ) as update:
        client = TestClient(app)
        r = client.patch(
            f"/memories/{memory_id}",
            headers={"Authorization": "Bearer tok"},
            json={"text": "Likes hiking"},
        )
    assert r.status_code == 200
    assert r.json()["text"] == "As of 2026-07-20: Likes hiking"
    update.assert_awaited_once()


def test_update_memory_not_found():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.memories.memory_service.update_memory", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.patch(
            f"/memories/{uuid4()}",
            headers={"Authorization": "Bearer tok"},
            json={"text": "Likes hiking"},
        )
    assert r.status_code == 404


def test_delete_memory_ok():
    user = _fake_user()
    app = _app_with_user(user)
    with patch("app.routers.memories.memory_service.delete_memory", AsyncMock(return_value=True)):
        client = TestClient(app)
        r = client.delete(f"/memories/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 204


def test_delete_memory_write_lock_busy_returns_409_not_404():
    """A background extraction/consolidation pass holds the memory write
    lock — the router must surface this as a distinct, retryable 409, not
    the same 404 it uses for "no such memory"."""
    from app.services import memory as memory_service

    user = _fake_user()
    app = _app_with_user(user)
    with patch(
        "app.routers.memories.memory_service.delete_memory",
        AsyncMock(side_effect=memory_service.MemoryWriteLockBusyError(user.id)),
    ):
        client = TestClient(app)
        r = client.delete(f"/memories/{uuid4()}", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 409


# ── webhooks / transactional email ────────────────────────────────────────────


def test_revenuecat_webhook_enqueues_receipt_on_purchase():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "app_user_id": str(uid),
            "store": "app_store",
            "product_id": "recall.pro.monthly",
            "expiration_at_ms": 1753977600000,
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ),
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()) as enq,
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    enq.assert_awaited_once()
    kwargs = enq.await_args.kwargs
    assert kwargs["event_type"] == "INITIAL_PURCHASE"
    assert kwargs["store"] == "app_store"
    assert kwargs["product_id"] == "recall.pro.monthly"
    assert kwargs["expiration"] is not None


def test_revenuecat_webhook_skips_receipt_when_plan_not_applied():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {"event": {"type": "INITIAL_PURCHASE", "app_user_id": str(uid)}}

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=False),
        ),
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()) as enq,
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    enq.assert_not_awaited()


def test_revenuecat_webhook_free_event_does_not_enqueue_receipt():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {"event": {"type": "EXPIRATION", "app_user_id": str(uid)}}

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ),
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()) as enq,
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    enq.assert_not_awaited()


def test_revenuecat_webhook_cancellation_with_future_expiry_keeps_pro():
    """CANCELLATION = auto-renew off; paid-through time must not be stripped."""
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    # Far-future paid-through timestamp (year 2099).
    payload = {
        "event": {
            "type": "CANCELLATION",
            "app_user_id": str(uid),
            "expiration_at_ms": 4099689600000,
        }
    }

    with patch(
        "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
        AsyncMock(return_value=True),
    ) as apply_plan:
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    apply_plan.assert_not_awaited()


def test_revenuecat_webhook_cancellation_with_past_expiry_downgrades():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "CANCELLATION",
            "app_user_id": str(uid),
            "expiration_at_ms": 1,
        }
    }

    with patch(
        "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
        AsyncMock(return_value=True),
    ) as apply_plan:
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    apply_plan.assert_awaited_once()
    assert apply_plan.await_args.kwargs["plan"] == "free"


def test_revenuecat_webhook_billing_issue_does_not_downgrade():
    """BILLING_ISSUE must not instantly set plan=free — wait for EXPIRATION."""
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {"event": {"type": "BILLING_ISSUE", "app_user_id": str(uid)}}

    with patch(
        "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
        AsyncMock(return_value=True),
    ) as apply_plan:
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    apply_plan.assert_not_awaited()


def test_revenuecat_webhook_expiration_still_downgrades():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {"event": {"type": "EXPIRATION", "app_user_id": str(uid)}}

    with patch(
        "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
        AsyncMock(return_value=True),
    ) as apply_plan:
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    apply_plan.assert_awaited_once()
    assert apply_plan.await_args.kwargs["plan"] == "free"


def test_revenuecat_webhook_ignores_stale_expiration_after_purchase():
    """INITIAL_PURCHASE then older EXPIRATION must not downgrade (plan stays pro)."""
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
        email_enabled=False,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    purchase = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "id": "evt-purchase",
            "app_user_id": str(uid),
            "event_timestamp_ms": 2000,
        }
    }
    stale_expiration = {
        "event": {
            "type": "EXPIRATION",
            "id": "evt-expire",
            "app_user_id": str(uid),
            "event_timestamp_ms": 1000,
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_plan,
        patch(
            "app.routers.webhooks.subscription_service.is_stale_rc_event",
            AsyncMock(side_effect=[False, True]),
        ),
        patch(
            "app.routers.webhooks.subscription_service.advance_rc_event_watermark",
            AsyncMock(),
        ) as advance,
    ):
        client = TestClient(app)
        assert client.post("/webhooks/revenuecat", json=purchase).status_code == 204
        assert client.post("/webhooks/revenuecat", json=stale_expiration).status_code == 204

    assert apply_plan.await_count == 1
    assert apply_plan.await_args.kwargs["plan"] == "pro"
    advance.assert_awaited_once()
    assert advance.await_args.args[2] == 2000


def test_revenuecat_webhook_newer_expiration_still_applies_after_purchase():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
        email_enabled=False,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    purchase = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "id": "evt-purchase-2",
            "app_user_id": str(uid),
            "event_timestamp_ms": 1000,
        }
    }
    expiration = {
        "event": {
            "type": "EXPIRATION",
            "id": "evt-expire-2",
            "app_user_id": str(uid),
            "event_timestamp_ms": 2000,
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_plan,
        patch(
            "app.routers.webhooks.subscription_service.is_stale_rc_event",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.routers.webhooks.subscription_service.advance_rc_event_watermark",
            AsyncMock(),
        ) as advance,
    ):
        client = TestClient(app)
        assert client.post("/webhooks/revenuecat", json=purchase).status_code == 204
        assert client.post("/webhooks/revenuecat", json=expiration).status_code == 204

    assert apply_plan.await_count == 2
    assert apply_plan.await_args_list[0].kwargs["plan"] == "pro"
    assert apply_plan.await_args_list[1].kwargs["plan"] == "free"
    assert [c.args[2] for c in advance.await_args_list] == [1000, 2000]


def test_expiration_overflow_ms_returns_none():
    """Huge expiration_at_ms must not raise (webhook 500 / retry storm)."""
    from app.routers.webhooks import _expiration

    assert _expiration({"event": {"expiration_at_ms": 10**20}}) is None
    assert _expiration({"event": {"expiration_at_ms": -(10**20)}}) is None


def test_revenuecat_webhook_huge_expiration_still_succeeds():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "app_user_id": str(uid),
            "expiration_at_ms": 10**20,
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ),
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()) as enq,
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    assert enq.await_args.kwargs.get("expiration") is None


def test_revenuecat_webhook_dedups_replay_by_event_id():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "event_id": "evt_123",
            "app_user_id": str(uid),
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()),
    ):
        client = TestClient(app)
        r1 = client.post("/webhooks/revenuecat", json=payload)
        r2 = client.post("/webhooks/revenuecat", json=payload)

    assert r1.status_code == 204
    assert r2.status_code == 204
    apply_mock.assert_awaited_once()


def test_revenuecat_webhook_missing_event_id_hashes_payload_for_dedupe():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "app_user_id": str(uid),
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()),
    ):
        client = TestClient(app)
        r1 = client.post("/webhooks/revenuecat", json=payload)
        r2 = client.post("/webhooks/revenuecat", json=payload)

    assert r1.status_code == 204
    assert r2.status_code == 204
    apply_mock.assert_awaited_once()


def test_revenuecat_webhook_pro_event_defers_when_entitlement_unresolved():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "event_id": "evt_unresolved",
            "app_user_id": str(uid),
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    apply_mock.assert_not_awaited()


def test_revenuecat_webhook_concurrent_claim_only_processes_once():
    """SET NX claim: two deliveries that both pass the done-marker check must
    not both dispatch — only the lock winner processes."""
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis
    from app.routers import webhooks as webhooks_mod

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "event_id": "evt_race",
            "app_user_id": str(uid),
        }
    }

    # First request claims; second sees lock held (simulate by pre-claiming).
    claim_results = iter([True, False])

    async def claim_side_effect(_redis, _event_id):
        return next(claim_results)

    with (
        patch.object(webhooks_mod, "_try_claim", side_effect=claim_side_effect),
        patch.object(webhooks_mod, "_already_processed", AsyncMock(return_value=False)),
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()) as enq,
    ):
        client = TestClient(app)
        r1 = client.post("/webhooks/revenuecat", json=payload)
        r2 = client.post("/webhooks/revenuecat", json=payload)

    assert r1.status_code == 204
    assert r2.status_code == 204
    apply_mock.assert_awaited_once()
    enq.assert_awaited_once()


def test_revenuecat_webhook_failed_processing_does_not_burn_dedup_key():
    """BUG FIX regression: a transient failure while processing an event must
    not mark the event id as seen — otherwise RevenueCat's legitimate retry
    of the same event_id would be silently swallowed by the dedup check,
    permanently losing the plan sync."""
    import fakeredis.aioredis
    import pytest

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "event_id": "evt_retry_1",
            "app_user_id": str(uid),
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(side_effect=[RuntimeError("boom"), True]),
        ) as apply_mock,
    ):
        client = TestClient(app)
        with pytest.raises(RuntimeError):
            client.post("/webhooks/revenuecat", json=payload)

        # The event id must not have been marked as seen by the failed attempt.
        r2 = client.post("/webhooks/revenuecat", json=payload)

    assert r2.status_code == 204
    assert apply_mock.await_count == 2


def test_revenuecat_webhook_requires_auth_in_production():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="production",
        revenuecat_webhook_auth="whsec-secret",
    )
    app.dependency_overrides[get_redis] = lambda: fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )

    payload = {"event": {"type": "INITIAL_PURCHASE", "app_user_id": str(uid)}}

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()),
    ):
        client = TestClient(app)
        r_bad = client.post("/webhooks/revenuecat", json=payload)
        r_ok = client.post(
            "/webhooks/revenuecat",
            json=payload,
            headers={"Authorization": "Bearer whsec-secret"},
        )

    assert r_bad.status_code == 401
    assert r_ok.status_code == 204
    apply_mock.assert_awaited_once()


def test_revenuecat_webhook_ignores_sandbox_in_production():
    """Sandbox INITIAL_PURCHASE must not grant Pro on a production host."""
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="production",
        revenuecat_webhook_auth="whsec-secret",
    )
    app.dependency_overrides[get_redis] = lambda: fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "app_user_id": str(uid),
            "environment": "SANDBOX",
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()) as enq,
    ):
        client = TestClient(app)
        r = client.post(
            "/webhooks/revenuecat",
            json=payload,
            headers={"Authorization": "Bearer whsec-secret"},
        )

    assert r.status_code == 204
    apply_mock.assert_not_awaited()
    enq.assert_not_awaited()


def test_revenuecat_webhook_processes_sandbox_in_development():
    """Local StoreKit testing still needs the webhook path to mutate plan."""
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    app.dependency_overrides[get_redis] = lambda: fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )

    payload = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "app_user_id": str(uid),
            "environment": "SANDBOX",
        }
    }

    with (
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
        patch("app.routers.webhooks.enqueue_purchase_receipt", AsyncMock()),
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    apply_mock.assert_awaited_once()


def test_revenuecat_webhook_transfer_downgrades_old_and_syncs_new():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    old_uid = uuid4()
    new_uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "TRANSFER",
            "app_user_id": str(new_uid),
            "transferred_from": [str(old_uid)],
        }
    }

    with patch(
        "app.routers.webhooks.subscription_service.handle_revenuecat_transfer",
        AsyncMock(),
    ) as transfer_mock:
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 204
    transfer_mock.assert_awaited_once()
    kwargs = transfer_mock.await_args.kwargs
    assert kwargs["new_app_user_id"] == str(new_uid)
    assert kwargs["transferred_from"] == [str(old_uid)]


def test_revenuecat_webhook_transfer_failure_does_not_dedup():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    old_uid = uuid4()
    new_uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "TRANSFER",
            "event_id": "evt_transfer_fail",
            "app_user_id": str(new_uid),
            "transferred_from": [str(old_uid)],
        }
    }

    with patch(
        "app.routers.webhooks.subscription_service.handle_revenuecat_transfer",
        AsyncMock(return_value=False),
    ) as transfer_mock:
        client = TestClient(app)
        r1 = client.post("/webhooks/revenuecat", json=payload)
        r2 = client.post("/webhooks/revenuecat", json=payload)

    assert r1.status_code == 204
    assert r2.status_code == 204
    assert transfer_mock.await_count == 2


def test_revenuecat_webhook_malformed_transfer_is_not_deduped():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "TRANSFER",
            "event_id": "evt_transfer_blank",
            "app_user_id": str(uid),
            "original_app_user_id": str(uid),
        }
    }
    # Blank target after strip — _dispatch_event must return False.
    payload["event"]["app_user_id"] = "   "

    with patch(
        "app.routers.webhooks.subscription_service.handle_revenuecat_transfer",
        AsyncMock(),
    ) as transfer_mock:
        client = TestClient(app)
        r1 = client.post("/webhooks/revenuecat", json=payload)
        r2 = client.post("/webhooks/revenuecat", json=payload)

    assert r1.status_code == 204
    assert r2.status_code == 204
    transfer_mock.assert_not_awaited()


def test_verify_auth_non_ascii_header_is_401():
    from fastapi import HTTPException

    from app.routers.webhooks import _verify_auth

    settings = Settings(revenuecat_webhook_auth="whsec-secret")
    with pytest.raises(HTTPException) as exc:
        _verify_auth("\x80whsec-secret", settings)
    assert exc.value.status_code == 401


def test_revenuecat_webhook_subscriber_lock_busy_returns_503():
    import fakeredis.aioredis

    from app.core.config import get_settings
    from app.core.deps import get_redis
    from app.routers import webhooks as webhooks_mod

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development",
        revenuecat_webhook_auth="",
        dev_allow_unauthed_webhooks=True,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {
        "event": {
            "type": "RENEWAL",
            "event_id": "evt_busy",
            "app_user_id": str(uid),
        }
    }

    with (
        patch.object(webhooks_mod, "acquire_lock", AsyncMock(return_value=None)),
        patch(
            "app.routers.webhooks.subscription_service.resolve_plan_from_revenuecat",
            AsyncMock(return_value="pro"),
        ),
        patch(
            "app.routers.webhooks.subscription_service.apply_plan_for_app_user_id",
            AsyncMock(return_value=True),
        ) as apply_mock,
    ):
        client = TestClient(app)
        r = client.post("/webhooks/revenuecat", json=payload)

    assert r.status_code == 503
    apply_mock.assert_not_awaited()


# ── admin DLQ ─────────────────────────────────────────────────────────────────


def test_admin_dlq_dev_gated_returns_403_in_production():
    user = _fake_user()
    app = _app_with_user(user)  # default Settings has dev_auth_enabled=True, but…

    with patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)):
        client = TestClient(app)
        # Settings() defaults dev_auth_enabled=True; force production behavior.
        from app.core.deps import get_settings_dep

        app.dependency_overrides[get_settings_dep] = lambda: Settings(dev_auth_enabled=False)
        r = client.get("/admin/dlq", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 403


def test_admin_dlq_list_and_replay_in_dev():
    user = _fake_user()
    app = _app_with_user(user)
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        admin_user_ids=str(user.id),
    )

    listed = [
        {
            "id": "1-0",
            "original_id": "0-0",
            "type": "memory",
            "payload": "{}",
            "error": "boom",
            "failed_at": "2026-07-02T00:00:00+00:00",
        }
    ]
    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
        patch("app.routers.admin.jobs.list_dlq", AsyncMock(return_value=listed)),
        patch("app.routers.admin.jobs.replay_dlq", AsyncMock(return_value=1)),
    ):
        client = TestClient(app)
        r_list = client.get("/admin/dlq", headers={"Authorization": "Bearer tok"})
        assert r_list.status_code == 200
        body = r_list.json()
        assert len(body) == 1
        assert body[0]["type"] == "memory"

        r_replay = client.post("/admin/dlq/replay", headers={"Authorization": "Bearer tok"})
        assert r_replay.status_code == 200
        assert r_replay.json()["replayed"] == 1


def test_admin_dlq_denies_non_allowlisted_user_in_dev():
    user = _fake_user()
    app = _app_with_user(user)
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        admin_user_ids=str(uuid4()),
    )

    with patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)):
        client = TestClient(app)
        r = client.get("/admin/dlq", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 403


def test_admin_dlq_denies_when_admin_allowlist_empty():
    user = _fake_user()
    app = _app_with_user(user)
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        admin_user_ids="",
    )

    with patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)):
        client = TestClient(app)
        r = client.get("/admin/dlq", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 403
    assert "ADMIN_USER_IDS" in r.json()["detail"]


def test_admin_dlq_count_is_bounded():
    user = _fake_user()
    app = _app_with_user(user)
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        admin_user_ids=str(user.id),
    )
    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
        patch("app.routers.admin.jobs.list_dlq", AsyncMock(return_value=[])),
        patch("app.routers.admin.jobs.replay_dlq", AsyncMock(return_value=0)),
    ):
        client = TestClient(app)
        headers = {"Authorization": "Bearer tok"}
        assert client.get("/admin/dlq?count=0", headers=headers).status_code == 422
        assert client.get("/admin/dlq?count=1000000", headers=headers).status_code == 422
        assert client.post("/admin/dlq/replay?count=-1", headers=headers).status_code == 422
        assert client.get("/admin/dlq?count=50", headers=headers).status_code == 200


def test_admin_dlq_skips_malformed_entries():
    user = _fake_user()
    app = _app_with_user(user)
    from app.core.deps import get_settings_dep

    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        dev_auth_enabled=True,
        admin_user_ids=str(user.id),
    )
    listed = [
        {
            "id": "1-0",
            "original_id": "0-0",
            "type": "memory",
            "payload": "{}",
            "error": "boom",
            "failed_at": "2026-07-02T00:00:00+00:00",
        },
        {"id": "2-0", "original_id": "1-0"},
    ]
    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
        patch("app.routers.admin.jobs.list_dlq", AsyncMock(return_value=listed)),
    ):
        client = TestClient(app)
        r = client.get("/admin/dlq", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == "1-0"


# ── speech ─────────────────────────────────────────────────────────────────────


def test_speech_transcribe_ok():
    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value="hello world"),
        ),
    ):
        r = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
    assert r.status_code == 200
    assert r.json()["text"] == "hello world"


def test_speech_transcribe_json_ok():
    import base64

    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    payload = {
        "audio_base64": base64.b64encode(b"fake-audio").decode(),
        "filename": "speech.m4a",
    }
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value="hello json"),
        ),
    ):
        r = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
            json=payload,
        )
    assert r.status_code == 200
    assert r.json()["text"] == "hello json"


def test_speech_transcribe_json_forwards_language():
    import base64

    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    payload = {
        "audio_base64": base64.b64encode(b"fake-audio").decode(),
        "filename": "speech.m4a",
        "language": "es-MX",
    }
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    transcribe = AsyncMock(return_value="hola")
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch("app.routers.speech.speech_service.transcribe_audio", transcribe),
    ):
        r = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
            json=payload,
        )
    assert r.status_code == 200
    assert r.json()["text"] == "hola"
    assert transcribe.await_args.kwargs["language"] == "es-MX"


def test_speech_transcribe_empty_text_ok():
    """Empty transcript is a valid no-speech result — 200 with empty text, not a 502 outage."""
    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value=""),
        ),
    ):
        r = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"silence", "audio/m4a")},
        )
    assert r.status_code == 200
    assert r.json()["text"] == ""


def test_speech_transcribe_provider_failure_is_502():
    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value=None),
        ),
    ):
        r = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
    assert r.status_code == 502


def test_speech_transcribe_daily_cap():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(daily_speech_transcriptions=1)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value="ok"),
        ),
    ):
        first = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
        second = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
    assert first.status_code == 200
    assert second.status_code == 429


def test_speech_transcribe_rate_limit():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        speech_rate_limit_per_minute=1,
        daily_speech_transcriptions=100,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value="ok"),
        ),
    ):
        first = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
        second = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
    assert first.status_code == 200
    assert second.status_code == 429


def test_speech_transcribe_disabled():
    user = _fake_user()
    from app.core.deps import get_current_user, get_settings_dep

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        speech_transcription_enabled=False
    )
    client = TestClient(app)
    r = client.post(
        "/speech/transcribe",
        headers={"Authorization": "Bearer tok"},
        files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
    )
    assert r.status_code == 404


def test_speech_transcribe_rejects_oversized_multipart_content_length():
    """Multipart uploads with a Content-Length over the limit must be rejected
    BEFORE the file is read into memory (memory-exhaustion DoS guard)."""
    import fakeredis.aioredis

    from app.models.schemas.integrations import SPEECH_MAX_REQUEST_BYTES

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    oversized = b"x" * (SPEECH_MAX_REQUEST_BYTES + 1)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value="should not reach"),
        ) as transcribe_mock,
    ):
        r = client.post(
            "/speech/transcribe",
            headers={
                "Authorization": "Bearer tok",
                "Content-Length": str(len(oversized)),
            },
            files={"file": ("speech.m4a", oversized, "audio/m4a")},
        )
    assert r.status_code == 413
    transcribe_mock.assert_not_awaited()


def test_speech_transcribe_6mb_is_413_before_quota():
    """6MB used to pass the 7.5MB body cap, reserve quota, then 502 at 5MB."""
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(daily_speech_transcriptions=1)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    six_mb = b"x" * 6_000_000
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.transcribe_audio",
            AsyncMock(return_value="ok"),
        ) as transcribe_mock,
    ):
        oversized = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", six_mb, "audio/m4a")},
        )
        ok = client.post(
            "/speech/transcribe",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("speech.m4a", b"fake-audio", "audio/m4a")},
        )
    assert oversized.status_code == 413
    assert ok.status_code == 200
    transcribe_mock.assert_awaited_once()


def test_speech_tts_ok():
    import base64

    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.synthesize_speech",
            AsyncMock(return_value=(b"fake-mp3", "audio/mpeg")),
        ),
    ):
        r = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "hello", "language": "en-US"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["content_type"] == "audio/mpeg"
    assert body["model"] == "speech-tts-model"
    assert base64.b64decode(body["audio_base64"]) == b"fake-mp3"


def test_speech_tts_cancelled_refunds():
    import asyncio

    import fakeredis.aioredis

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def boom(*_args: object, **_kwargs: object) -> tuple[bytes, str]:
        raise asyncio.CancelledError()

    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch("app.routers.speech.speech_service.synthesize_speech", boom),
        patch(
            "app.routers.speech.quota_service.refund_speech_tts",
            AsyncMock(),
        ) as refund,
    ):
        with pytest.raises((asyncio.CancelledError, RuntimeError)):
            client.post(
                "/speech/tts",
                headers={"Authorization": "Bearer tok"},
                json={"text": "hello"},
            )
    refund.assert_awaited()


def test_speech_tts_daily_cap():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(daily_speech_tts=1)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.synthesize_speech",
            AsyncMock(return_value=(b"ok", "audio/mpeg")),
        ),
    ):
        first = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "one"},
        )
        second = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "two"},
        )
    assert first.status_code == 200
    assert second.status_code == 429
    assert "read-aloud" in second.json()["detail"].lower()


def test_speech_tts_lead_allows_multiple_rest_followups():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(daily_speech_tts=1)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.synthesize_speech",
            AsyncMock(return_value=(b"ok", "audio/mpeg")),
        ),
    ):
        lead = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "first clip", "part": "lead"},
        )
        lead_hash = lead.json()["lead_hash"]
        rest_one = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "second clip", "part": "rest", "lead_hash": lead_hash},
        )
        rest_two = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "third clip", "part": "rest", "lead_hash": lead_hash},
        )
        extra_full = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "another page", "part": "full"},
        )
    assert lead.status_code == 200
    assert rest_one.status_code == 200
    assert rest_two.status_code == 200
    assert extra_full.status_code == 429


def test_speech_tts_rest_wrong_lead_hash_is_billed():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(daily_speech_tts=1)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.synthesize_speech",
            AsyncMock(return_value=(b"ok", "audio/mpeg")),
        ),
    ):
        lead = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "first clip", "part": "lead"},
        )
        wrong = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={
                "text": "other utterance rest",
                "part": "rest",
                "lead_hash": "deadbeefdeadbeef",
            },
        )
        matched = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={
                "text": "second clip",
                "part": "rest",
                "lead_hash": lead.json()["lead_hash"],
            },
        )
    assert lead.status_code == 200
    assert lead.json()["lead_hash"]
    assert wrong.status_code == 429
    assert matched.status_code == 200


def test_speech_tts_rest_over_char_budget_is_billed():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(daily_speech_tts=1)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.synthesize_speech",
            AsyncMock(return_value=(b"ok", "audio/mpeg")),
        ),
    ):
        lead = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "hi", "part": "lead"},
        )
        rest_over = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={
                "text": "x" * 3999,
                "part": "rest",
                "lead_hash": lead.json()["lead_hash"],
            },
        )
    assert lead.status_code == 200
    assert rest_over.status_code == 429


def test_speech_tts_rate_limit_message():
    import fakeredis.aioredis

    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        speech_rate_limit_per_minute=1,
        daily_speech_tts=100,
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = TestClient(app)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.synthesize_speech",
            AsyncMock(return_value=(b"ok", "audio/mpeg")),
        ),
    ):
        first = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "one"},
        )
        second = client.post(
            "/speech/tts",
            headers={"Authorization": "Bearer tok"},
            json={"text": "two"},
        )
    assert first.status_code == 200
    assert second.status_code == 429
    assert "read-aloud" in second.json()["detail"].lower()


def test_speech_tts_disabled():
    user = _fake_user()
    from app.core.deps import get_current_user, get_settings_dep

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(speech_tts_enabled=False)
    client = TestClient(app)
    r = client.post(
        "/speech/tts",
        headers={"Authorization": "Bearer tok"},
        json={"text": "hello"},
    )
    assert r.status_code == 404


def test_speech_tts_stream_ok():
    import fakeredis.aioredis

    async def _chunks(*_args, **_kwargs):
        yield b"pcm"
        yield b"-hi"

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.speech_service.iter_tts_pcm",
            _chunks,
        ),
    ):
        r = client.post(
            "/speech/tts/stream",
            headers={"Authorization": "Bearer tok"},
            json={"text": "hello", "language": "en-US"},
        )
    assert r.status_code == 200
    assert r.content == b"pcm-hi"
    assert "L16" in r.headers.get("content-type", "")


def test_speech_tts_stream_empty_refunds():
    import fakeredis.aioredis

    async def _empty(*_args, **_kwargs):
        if False:
            yield b"x"

    user = _fake_user()
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch("app.routers.speech.speech_service.iter_tts_pcm", _empty),
        patch(
            "app.routers.speech.quota_service.refund_speech_tts",
            AsyncMock(),
        ) as refund,
    ):
        r = client.post(
            "/speech/tts/stream",
            headers={"Authorization": "Bearer tok"},
            json={"text": "hello"},
        )
    assert r.status_code == 200
    assert r.content == b""
    refund.assert_awaited()


def test_speech_live_status_free_not_entitled():
    import fakeredis.aioredis

    user = _fake_user(plan="free")
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.routers.speech.get_redis_client", return_value=fake_redis):
        r = client.get("/speech/live", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["entitled"] is False
    assert body["remaining"] == 0
    assert body["limit"] == 0


def test_speech_live_status_pro_remaining():
    import fakeredis.aioredis

    user = _fake_user(plan="pro")
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.routers.speech.get_redis_client", return_value=fake_redis):
        r = client.get("/speech/live", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    body = r.json()
    assert body["entitled"] is True
    assert body["remaining"] == 30
    assert body["limit"] == 30


def test_speech_live_turn_gone():
    user = _fake_user(plan="free")
    client = TestClient(_app_with_user(user))
    r = client.post("/speech/live/turn", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 410
    assert "speak" in r.json()["detail"].lower()


def test_speech_live_turn_pro_also_gone():
    user = _fake_user(plan="pro")
    client = TestClient(_app_with_user(user))
    r = client.post("/speech/live/turn", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 410


@pytest.mark.asyncio
async def test_speech_live_refund_pending_slot():
    import fakeredis.aioredis
    from httpx import ASGITransport, AsyncClient

    from app.services import quota as quota_service

    user = _fake_user(plan="pro")
    app = _app_with_user(user)
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await quota_service.reserve_live_talk(fake_redis, user.id, limit=30)
    with patch("app.routers.speech.get_redis_client", return_value=fake_redis):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            refund = await client.post(
                "/speech/live/refund",
                headers={"Authorization": "Bearer tok"},
            )
            again = await client.post(
                "/speech/live/refund",
                headers={"Authorization": "Bearer tok"},
            )
    assert refund.status_code == 200
    assert refund.json()["refunded"] is True
    assert refund.json()["remaining"] == 30
    assert again.json()["refunded"] is False


def test_speech_live_commit_gone():
    user = _fake_user(plan="pro")
    client = TestClient(_app_with_user(user))
    r = client.post("/speech/live/commit", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 410


def test_speech_live_speak_requires_pro():
    import fakeredis.aioredis

    user = _fake_user(plan="free")
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.routers.speech.get_redis_client", return_value=fake_redis):
        r = client.post(
            "/speech/live/speak",
            headers={"Authorization": "Bearer tok"},
            json={"audio_base64": "YWJj", "filename": "speech.m4a"},
        )
    assert r.status_code == 403


def test_speech_live_speak_pro_returns_audio():
    import base64

    import fakeredis.aioredis

    from app.services.live_talk_stream import LiveTalkStreamEvent

    user = _fake_user(plan="pro")
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    wav = b"RIFF" + b"\x00" * 12

    async def fake_iter(*_args: object, **_kwargs: object):
        yield LiveTalkStreamEvent(kind="user", text="Hi there")
        yield LiveTalkStreamEvent(kind="audio", audio_wav=wav)
        yield LiveTalkStreamEvent(kind="assistant", text="Hello")

    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.speech.iter_speech_to_speech",
            fake_iter,
        ),
    ):
        r = client.post(
            "/speech/live/speak",
            headers={"Authorization": "Bearer tok"},
            json={
                "audio_base64": base64.b64encode(b"abc").decode("ascii"),
                "filename": "speech.wav",
            },
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert '"type": "audio"' in r.text
    assert "Hello" in r.text
    assert '"type": "done"' in r.text
    assert '"remaining"' in r.text


def test_speech_live_speak_text_reply_without_audio_still_dones():
    import base64

    import fakeredis.aioredis

    from app.services.live_talk_stream import LiveTalkStreamEvent

    user = _fake_user(plan="pro")
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def fake_iter(*_args: object, **_kwargs: object):
        yield LiveTalkStreamEvent(kind="user", text="Hi there")
        yield LiveTalkStreamEvent(kind="assistant", text="Hello")

    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch("app.routers.speech.iter_speech_to_speech", fake_iter),
    ):
        r = client.post(
            "/speech/live/speak",
            headers={"Authorization": "Bearer tok"},
            json={
                "audio_base64": base64.b64encode(b"abc").decode("ascii"),
                "filename": "speech.wav",
            },
        )
    assert r.status_code == 200
    assert '"type": "error"' not in r.text
    assert "Hello" in r.text
    assert '"type": "done"' in r.text


def test_speech_live_speak_empty_transcript_errors_without_audio():
    import base64

    import fakeredis.aioredis

    from app.services.live_talk_stream import LIVE_TALK_EMPTY_TRANSCRIPT, LiveTalkStreamEvent

    user = _fake_user(plan="pro")
    client = TestClient(_app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def fake_iter(*_args: object, **_kwargs: object):
        yield LiveTalkStreamEvent(kind="error", text=LIVE_TALK_EMPTY_TRANSCRIPT)

    with (
        patch("app.routers.speech.get_redis_client", return_value=fake_redis),
        patch("app.routers.speech.iter_speech_to_speech", fake_iter),
    ):
        r = client.post(
            "/speech/live/speak",
            headers={"Authorization": "Bearer tok"},
            json={
                "audio_base64": base64.b64encode(b"abc").decode("ascii"),
                "filename": "speech.wav",
            },
        )
    assert r.status_code == 200
    assert LIVE_TALK_EMPTY_TRANSCRIPT in r.text
    assert '"type": "audio"' not in r.text


def test_speech_live_disabled():
    from app.core.deps import get_current_user, get_settings_dep

    user = _fake_user(plan="pro")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings(speech_live_talk_enabled=False)
    client = TestClient(app)
    r = client.get("/speech/live", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    denied = client.post("/speech/live/turn", headers={"Authorization": "Bearer tok"})
    assert denied.status_code == 404
