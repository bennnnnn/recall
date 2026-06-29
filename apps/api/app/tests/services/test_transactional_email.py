from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways import email_gateway
from app.services import transactional_email as tx_email


def _user(*, email="user@test.local", name="Ada", locale=None):
    user = MagicMock()
    user.id = uuid4()
    user.email = email
    user.name = name
    user.locale = locale
    return user


def test_build_welcome_uses_name_and_en_default():
    user = _user(name="Ada", locale="fr")
    subject, html, text = tx_email.build_welcome(user)
    assert subject == "Welcome to Recall"
    assert "Ada" in text
    assert "Ada" in html
    # French locale falls back to English template (no fr bundle authored yet).
    assert "Welcome to Recall" in text


def test_build_welcome_falls_back_to_greeting_when_no_name():
    user = _user(name="", locale="en")
    _, _, text = tx_email.build_welcome(user)
    assert "Hi there" in text


def test_build_receipt_includes_event_and_optional_fields():
    user = _user(name="Bo", locale="en")
    subject, html, text = tx_email.build_receipt(
        user,
        event_type="INITIAL_PURCHASE",
        store="app_store",
        product_id="recall.pro.monthly",
        expiration="2026-08-01T00:00:00+00:00",
    )
    assert subject == "Your Recall Pro receipt"
    assert "INITIAL_PURCHASE" in text
    assert "app_store" in text
    assert "recall.pro.monthly" in text
    assert "2026-08-01T00:00:00+00:00" in text
    assert "INITIAL_PURCHASE" in html


def test_build_receipt_without_optional_fields_does_not_render_placeholders():
    user = _user(name="Bo", locale="en")
    _, _, text = tx_email.build_receipt(user, event_type="RENEWAL")
    assert "RENEWAL" in text
    # No expiration line when not provided.
    assert "Renews:" not in text


@pytest.mark.asyncio
async def test_send_welcome_dispatches_via_gateway():
    settings = Settings()
    user = _user(name="Ada", locale="en")
    with patch.object(email_gateway, "send_email", AsyncMock(return_value=True)) as mocked:
        ok = await tx_email.send_welcome(settings, user)
    assert ok is True
    assert mocked.await_count == 1
    kwargs = mocked.await_args.kwargs
    assert kwargs["to"] == "user@test.local"
    assert kwargs["subject"] == "Welcome to Recall"
    assert "Ada" in kwargs["text"]


@pytest.mark.asyncio
async def test_send_purchase_receipt_dispatches_via_gateway():
    settings = Settings()
    user = _user(name="Bo", locale="en")
    with patch.object(email_gateway, "send_email", AsyncMock(return_value=True)) as mocked:
        ok = await tx_email.send_purchase_receipt(
            settings, user, event_type="RENEWAL", store="app_store"
        )
    assert ok is True
    kwargs = mocked.await_args.kwargs
    assert kwargs["subject"] == "Your Recall Pro receipt"
    assert "RENEWAL" in kwargs["text"]


@pytest.mark.asyncio
async def test_gateway_mock_path_logs_when_no_key():
    settings = Settings()  # no resend_api_key by default
    assert email_gateway.is_configured(settings) is False
    # Should not raise and should return True (mocked send).
    ok = await email_gateway.send_email(settings, to="x@y.com", subject="s", html="<p/>", text="t")
    assert ok is True


@pytest.mark.asyncio
async def test_gateway_skips_when_disabled():
    settings = Settings(email_enabled=False)
    ok = await email_gateway.send_email(settings, to="x@y.com", subject="s", html="<p/>", text="t")
    assert ok is False


@pytest.mark.asyncio
async def test_gateway_skips_empty_recipient():
    settings = Settings()
    ok = await email_gateway.send_email(settings, to="   ", subject="s", html="<p/>", text="t")
    assert ok is False


@pytest.mark.asyncio
async def test_gateway_real_path_posts_to_resend(monkeypatch):
    settings = Settings(resend_api_key="rk_test", email_from="Recall <noreply@recall.app>")
    assert email_gateway.is_configured(settings) is True

    captured: dict = {}

    class FakeResp:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

    monkeypatch.setattr("app.gateways.email_gateway.httpx.AsyncClient", FakeClient)
    ok = await email_gateway.send_email(
        settings, to="a@b.com", subject="Hi", html="<p>Hi</p>", text="Hi"
    )
    assert ok is True
    assert captured["url"] == settings.resend_api_url
    assert captured["headers"]["Authorization"] == "Bearer rk_test"
    assert captured["json"]["to"] == "a@b.com"
    assert captured["json"]["from"] == "Recall <noreply@recall.app>"


@pytest.mark.asyncio
async def test_gateway_real_path_swallows_errors(monkeypatch):
    settings = Settings(resend_api_key="rk_test")

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr("app.gateways.email_gateway.httpx.AsyncClient", FakeClient)
    # Must not raise.
    ok = await email_gateway.send_email(settings, to="a@b.com", subject="Hi", html="<p/>", text="t")
    assert ok is False


# ── job enqueue + handler ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enqueue_welcome_email_xadds_to_jobs_stream():
    import fakeredis.aioredis

    from app.core import jobs

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    uid = uuid4()
    await jobs.enqueue_welcome_email(redis, uid)
    entries = await redis.xrange(jobs.JOBS_STREAM)
    assert len(entries) == 1
    _, fields = entries[0]
    import json

    payload = json.loads(fields["payload"])
    assert fields["type"] == "transactional_email"
    assert payload == {"kind": "welcome", "user_id": str(uid)}


@pytest.mark.asyncio
async def test_enqueue_purchase_receipt_payload_shape():
    import json

    import fakeredis.aioredis

    from app.core import jobs

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    uid = uuid4()
    await jobs.enqueue_purchase_receipt(
        redis,
        uid,
        event_type="RENEWAL",
        store="app_store",
        product_id="recall.pro.monthly",
        expiration="2026-08-01T00:00:00+00:00",
    )
    entries = await redis.xrange(jobs.JOBS_STREAM)
    _, fields = entries[0]
    payload = json.loads(fields["payload"])
    assert payload["kind"] == "receipt"
    assert payload["event_type"] == "RENEWAL"
    assert payload["store"] == "app_store"
    assert payload["user_id"] == str(uid)


@pytest.mark.asyncio
async def test_handle_transactional_email_welcome_dispatches():
    from app.core import jobs

    uid = uuid4()
    user = _user(name="Ada", locale="en")

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    settings = Settings()

    with (
        patch("app.core.jobs.SessionLocal", return_value=FakeSession()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch.object(tx_email, "send_welcome", AsyncMock(return_value=True)) as send,
    ):
        await jobs._handle_transactional_email(settings, {"kind": "welcome", "user_id": str(uid)})
    send.assert_awaited_once_with(settings, user)


@pytest.mark.asyncio
async def test_handle_transactional_email_receipt_dispatches():
    from app.core import jobs

    uid = uuid4()
    user = _user(name="Bo", locale="en")

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    settings = Settings()

    with (
        patch("app.core.jobs.SessionLocal", return_value=FakeSession()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch.object(tx_email, "send_purchase_receipt", AsyncMock(return_value=True)) as send,
    ):
        await jobs._handle_transactional_email(
            settings,
            {
                "kind": "receipt",
                "user_id": str(uid),
                "event_type": "RENEWAL",
                "store": "app_store",
                "product_id": "p",
                "expiration": "2026-08-01T00:00:00+00:00",
            },
        )
    send.assert_awaited_once()
    kwargs = send.await_args.kwargs
    assert kwargs["event_type"] == "RENEWAL"
    assert kwargs["store"] == "app_store"


@pytest.mark.asyncio
async def test_handle_transactional_email_unknown_kind_does_nothing():
    from app.core import jobs

    uid = uuid4()
    user = _user()

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    with (
        patch("app.core.jobs.SessionLocal", return_value=FakeSession()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch.object(tx_email, "send_welcome", AsyncMock()) as send_w,
        patch.object(tx_email, "send_purchase_receipt", AsyncMock()) as send_r,
    ):
        await jobs._handle_transactional_email(Settings(), {"kind": "bogus", "user_id": str(uid)})
    send_w.assert_not_awaited()
    send_r.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_transactional_email_missing_user_is_noop():
    from app.core import jobs

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    with (
        patch("app.core.jobs.SessionLocal", return_value=FakeSession()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=None)),
        patch.object(tx_email, "send_welcome", AsyncMock()) as send,
    ):
        await jobs._handle_transactional_email(
            Settings(), {"kind": "welcome", "user_id": str(uuid4())}
        )
    send.assert_not_awaited()


# ── auth signup enqueues welcome ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_dev_enqueues_welcome_for_new_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    settings = Settings(dev_auth_enabled=True, jwt_secret="test-secret-long-enough-32-chars!!")
    redis = AsyncMock()
    fake_user_out = UserOut(
        id=uuid4(),
        email="dev@test.local",
        name="Dev",
        avatar_url=None,
        default_model="auto",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )

    with (
        patch("app.services.auth.users_repo.get_by_google_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.create", AsyncMock(return_value=MagicMock(id=uuid4()))),
        patch("app.services.auth.create_access_token", return_value="tok"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
        patch("app.services.auth.jobs.enqueue_welcome_email", AsyncMock()) as enq,
    ):
        await auth_service.login_dev(
            AsyncMock(), settings, email="dev@test.local", name="Dev", redis=redis
        )
    enq.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_dev_does_not_enqueue_for_existing_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    settings = Settings(dev_auth_enabled=True, jwt_secret="test-secret-long-enough-32-chars!!")
    redis = AsyncMock()
    existing = MagicMock(id=uuid4())
    fake_user_out = UserOut(
        id=uuid4(),
        email="dev@test.local",
        name="Dev",
        avatar_url=None,
        default_model="auto",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )

    with (
        patch("app.services.auth.users_repo.get_by_google_sub", AsyncMock(return_value=existing)),
        patch("app.services.auth.create_access_token", return_value="tok"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
        patch("app.services.auth.jobs.enqueue_welcome_email", AsyncMock()) as enq,
    ):
        await auth_service.login_dev(
            AsyncMock(), settings, email="dev@test.local", name="Dev", redis=redis
        )
    enq.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_dev_skips_enqueue_when_email_disabled():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    settings = Settings(
        dev_auth_enabled=True,
        email_enabled=False,
        jwt_secret="test-secret-long-enough-32-chars!!",
    )
    redis = AsyncMock()
    fake_user_out = UserOut(
        id=uuid4(),
        email="dev@test.local",
        name="Dev",
        avatar_url=None,
        default_model="auto",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )

    with (
        patch("app.services.auth.users_repo.get_by_google_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.create", AsyncMock(return_value=MagicMock(id=uuid4()))),
        patch("app.services.auth.create_access_token", return_value="tok"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
        patch("app.services.auth.jobs.enqueue_welcome_email", AsyncMock()) as enq,
    ):
        await auth_service.login_dev(
            AsyncMock(), settings, email="dev@test.local", name="Dev", redis=redis
        )
    enq.assert_not_awaited()
