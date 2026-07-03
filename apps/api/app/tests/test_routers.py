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
    u.location_enabled = kw.get("location_enabled", bool(kw.get("location")))
    u.custom_instructions = kw.get("custom_instructions", None)
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


def test_me_patch_invalidates_memory_cache_on_toggle():
    user = _fake_user()
    user.memory_enabled = True
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()

    with (
        patch("app.routers.auth.users_repo.update", AsyncMock(return_value=user)),
        patch(
            "app.routers.auth.memory_service.invalidate_memory_block",
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


def test_me_patch_skips_memory_invalidation_when_unchanged():
    user = _fake_user()
    user.memory_enabled = True
    app = _app_with_user(user)
    invalidate_mock = AsyncMock()

    with (
        patch("app.routers.auth.users_repo.update", AsyncMock(return_value=user)),
        patch(
            "app.routers.auth.memory_service.invalidate_memory_block",
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
        patch("app.routers.auth.users_repo.update", AsyncMock(side_effect=capture)),
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
        patch("app.routers.auth.users_repo.update", AsyncMock(side_effect=capture)),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        r2 = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer tok"},
            json={"custom_instructions": "   "},
        )
    assert r2.status_code == 200
    assert captured["custom_instructions"] is None


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


def test_create_chat_with_other_users_project_id_rejected():
    from app.models.orm import Chat

    user = _fake_user()
    app = _app_with_user(user)
    chat = MagicMock(spec=Chat)
    chat.id = uuid4()
    chat.title = None
    chat.model = "free-chat"
    chat.pinned = False
    chat.project_id = None
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    # project_id that doesn't belong to the user → projects_repo.get_by_id
    # returns None → router must 400 instead of linking to a foreign project.
    pid = uuid4()
    with patch("app.routers.chats.projects_repo.get_by_id", AsyncMock(return_value=None)):
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
    chat.project_id = pid
    chat.created_at = datetime(2024, 1, 1)
    chat.updated_at = datetime(2024, 1, 1)

    project = MagicMock()
    project.id = pid
    project.user_id = user.id
    with (
        patch("app.routers.chats.projects_repo.get_by_id", AsyncMock(return_value=project)),
        patch("app.routers.chats.chats_repo.create", AsyncMock(return_value=chat)),
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
        patch("app.routers.chats.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.routers.chats.messages_repo.list_page",
            AsyncMock(return_value=([user_msg, asst_msg], False)),
        ),
        patch("app.routers.chats.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        client = TestClient(app)
        r = client.get(f"/chats/{chat_id}/messages", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 200
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

    with patch("app.routers.chats.chats_repo.get_by_id", AsyncMock(return_value=chat)):
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

    with patch("app.routers.chats.usage_repo.get_for_date", AsyncMock(return_value=None)):
        client = TestClient(app)
        r = client.get("/chats/usage/today", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    data = r.json()
    assert "remaining" in data
    assert "used_tokens" in data
    assert data["remaining"] == data["daily_limit"] - data["used_tokens"]


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

    with patch("app.routers.chats.usage_repo.get_for_date", AsyncMock(return_value=db_usage)):
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


# ── webhooks / transactional email ────────────────────────────────────────────


def test_revenuecat_webhook_enqueues_receipt_on_purchase():
    import fakeredis.aioredis

    from app.core.deps import get_redis, get_settings_dep

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: Settings(environment="development")
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

    from app.core.deps import get_redis, get_settings_dep

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: Settings(environment="development")
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {"event": {"type": "INITIAL_PURCHASE", "app_user_id": str(uid)}}

    with (
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

    from app.core.deps import get_redis, get_settings_dep

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: Settings(environment="development")
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: fake_redis

    payload = {"event": {"type": "CANCELLATION", "app_user_id": str(uid)}}

    with (
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


def test_revenuecat_webhook_dedups_replay_by_event_id():
    import fakeredis.aioredis

    from app.core.deps import get_redis, get_settings_dep

    uid = uuid4()
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: Settings(environment="development")
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
