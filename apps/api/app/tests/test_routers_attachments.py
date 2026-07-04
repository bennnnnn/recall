"""Attachment router tests."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.gateways.storage_gateway import (
    LocalStorageGateway,
    PresignedUpload,
    UnconfiguredStorageGateway,
)
from app.main import create_app
from app.models.orm import User


def _fake_user() -> User:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.email = "test@recall.local"
    return u


def _app_with_user(user: User):
    from app.core.deps import get_current_user

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings()
    return app


def test_presign_upload_rejects_bad_content_type():
    user = _fake_user()
    client = TestClient(_app_with_user(user))
    r = client.post(
        "/attachments/presign",
        headers={"Authorization": "Bearer tok"},
        json={"content_type": "application/x-msdownload", "size_bytes": 100},
    )
    assert r.status_code == 400


def test_presign_upload_success():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    gateway = MagicMock(spec=LocalStorageGateway)
    gateway.presign_upload = AsyncMock(
        return_value=PresignedUpload(
            attachment_id=str(attachment_id),
            upload_url=f"/attachments/{attachment_id}/upload",
            storage_key=f"{user.id}/{attachment_id}",
            headers={"Content-Type": "image/png"},
            api_upload=True,
        )
    )
    fake_redis = AsyncMock()
    fake_redis.incrby = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock()

    with (
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
        patch("app.routers.attachments.attachments_repo.create_pending", AsyncMock()),
        patch("app.routers.attachments.get_redis_client", return_value=fake_redis),
    ):
        client = TestClient(app)
        r = client.post(
            "/attachments/presign",
            headers={"Authorization": "Bearer tok"},
            json={"content_type": "image/png", "size_bytes": 128},
        )

    assert r.status_code == 200
    assert r.json()["attachment_id"] == str(attachment_id)


def test_presign_upload_returns_503_when_storage_unconfigured():
    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = AsyncMock()
    fake_redis.incrby = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock()

    with (
        patch(
            "app.routers.attachments.get_storage_gateway",
            return_value=UnconfiguredStorageGateway(),
        ),
        patch("app.routers.attachments.get_redis_client", return_value=fake_redis),
    ):
        client = TestClient(app)
        r = client.post(
            "/attachments/presign",
            headers={"Authorization": "Bearer tok"},
            json={"content_type": "image/png", "size_bytes": 128},
        )

    assert r.status_code == 503
    fake_redis.incrby.assert_not_called()


def test_cancel_pending_upload_refunds_image_quota():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id
    row.message_id = None
    row.content_type = "image/png"
    row.storage_key = "user/key"

    gateway = MagicMock()
    gateway.delete_bytes = AsyncMock()
    fake_redis = AsyncMock()
    refund_mock = AsyncMock()

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch(
            "app.routers.attachments.attachments_repo.delete_rows",
            AsyncMock(return_value=1),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
        patch("app.routers.attachments.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.attachments.quota_service.refund_image_upload",
            refund_mock,
        ),
    ):
        client = TestClient(app)
        r = client.delete(
            f"/attachments/{attachment_id}",
            headers={"Authorization": "Bearer tok"},
        )

    assert r.status_code == 204
    refund_mock.assert_awaited_once_with(fake_redis, user.id)


def test_confirm_upload_rejects_spoofed_r2_bytes():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = "user/key"
    row.size_bytes = 128

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"not-a-png")
    gateway.delete_bytes = AsyncMock()
    fake_redis = AsyncMock()
    refund_mock = AsyncMock()

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
        patch("app.routers.attachments.get_redis_client", return_value=fake_redis),
        patch(
            "app.routers.attachments.quota_service.refund_image_upload",
            refund_mock,
        ),
        patch(
            "app.routers.attachments.attachments_repo.delete_rows",
            AsyncMock(return_value=1),
        ) as delete_rows,
    ):
        client = TestClient(app)
        r = client.post(
            f"/attachments/{attachment_id}/confirm",
            headers={"Authorization": "Bearer tok"},
        )

    assert r.status_code == 400
    gateway.delete_bytes.assert_awaited_once_with("user/key")
    delete_rows.assert_awaited_once()
    refund_mock.assert_awaited_once_with(fake_redis, user.id)


def test_confirm_upload_accepts_valid_r2_bytes():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = "user/key"
    row.size_bytes = 128
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 10

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=png_bytes)

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
    ):
        client = TestClient(app)
        r = client.post(
            f"/attachments/{attachment_id}/confirm",
            headers={"Authorization": "Bearer tok"},
        )

    assert r.status_code == 204


def test_confirm_upload_noop_for_local_backend():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id

    gateway = MagicMock(spec=LocalStorageGateway)

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
    ):
        client = TestClient(app)
        r = client.post(
            f"/attachments/{attachment_id}/confirm",
            headers={"Authorization": "Bearer tok"},
        )

    assert r.status_code == 204


def test_presign_upload_rejects_image_over_daily_limit():
    user = _fake_user()
    app = _app_with_user(user)
    fake_redis = AsyncMock()

    async def _incrby_over_limit(key, amount):
        return 6

    fake_redis.incrby = _incrby_over_limit
    fake_redis.expire = AsyncMock()

    with patch("app.routers.attachments.get_redis_client", return_value=fake_redis):
        client = TestClient(app)
        r = client.post(
            "/attachments/presign",
            headers={"Authorization": "Bearer tok"},
            json={"content_type": "image/png", "size_bytes": 128},
        )

    assert r.status_code == 429


def test_upload_rejects_bytes_not_matching_claimed_content_type():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = f"{user.id}/{attachment_id}"
    gateway = MagicMock(spec=LocalStorageGateway)
    gateway.write_bytes = AsyncMock()

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
        patch("app.routers.attachments.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.routers.attachments.quota_service.refund_image_upload",
            AsyncMock(),
        ) as refund_mock,
    ):
        client = TestClient(app)
        r = client.put(
            f"/attachments/{attachment_id}/upload",
            headers={"Authorization": "Bearer tok"},
            content=b"#!/bin/sh\nrm -rf /\n",
        )

    assert r.status_code == 400
    gateway.write_bytes.assert_not_awaited()
    refund_mock.assert_awaited_once()


def test_upload_accepts_bytes_matching_claimed_content_type():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = f"{user.id}/{attachment_id}"
    gateway = MagicMock(spec=LocalStorageGateway)
    gateway.write_bytes = AsyncMock()

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
    ):
        client = TestClient(app)
        r = client.put(
            f"/attachments/{attachment_id}/upload",
            headers={"Authorization": "Bearer tok"},
            content=png_bytes,
        )

    assert r.status_code == 204
    gateway.write_bytes.assert_awaited_once()


def test_download_url_local_backend():
    user = _fake_user()
    app = _app_with_user(user)
    attachment_id = uuid4()
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.size_bytes = 128
    row.storage_key = "key"
    row.created_at = datetime(2024, 1, 1)

    gateway = MagicMock(spec=LocalStorageGateway)

    with (
        patch(
            "app.routers.attachments.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
    ):
        client = TestClient(app)
        r = client.get(
            f"/attachments/{attachment_id}/url",
            headers={"Authorization": "Bearer tok"},
        )

    assert r.status_code == 200
    assert r.json()["download_url"] == f"/attachments/{attachment_id}/file"
