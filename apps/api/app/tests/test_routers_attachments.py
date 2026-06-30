"""Attachment router tests."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.gateways.storage_gateway import LocalStorageGateway, PresignedUpload
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

    with (
        patch("app.routers.attachments.get_storage_gateway", return_value=gateway),
        patch("app.routers.attachments.attachments_repo.create_pending", AsyncMock()),
    ):
        client = TestClient(app)
        r = client.post(
            "/attachments/presign",
            headers={"Authorization": "Bearer tok"},
            json={"content_type": "image/png", "size_bytes": 128},
        )

    assert r.status_code == 200
    assert r.json()["attachment_id"] == str(attachment_id)


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
