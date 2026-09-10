import base64
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.orm import User
from app.services.math_ocr import MathOcrResult


def _fake_user() -> User:
    from datetime import datetime
    from unittest.mock import MagicMock

    u = MagicMock(spec=User)
    u.id = uuid4()
    u.email = "test@recall.local"
    u.plan = "free"
    u.created_at = datetime(2024, 1, 1)
    return u


def _app(user: User, settings: Settings | None = None):
    from app.core.deps import get_current_user, get_settings_dep

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings or Settings(
        math_scan_extract_per_minute=20,
        mock_llm_enabled=True,
    )
    return app


def test_scan_extract_returns_ocr_readback():
    user = _fake_user()
    client = TestClient(_app(user))
    image_b64 = base64.b64encode(b"fake-bytes").decode("ascii")
    result = MathOcrResult(
        extract=None,
        display_text="2*x+7 = 15",
        source="mathpix",
        confidence=0.94,
        uncertain=False,
    )
    with (
        patch("app.routers.math_scan.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.routers.math_scan.allow_request_fail_closed",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.routers.math_scan.extract_math_from_image",
            AsyncMock(return_value=result),
        ),
    ):
        response = client.post(
            "/math/scan-extract",
            headers={"Authorization": "Bearer tok"},
            json={"image_base64": image_b64, "content_type": "image/jpeg"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["display_text"] == "2*x+7 = 15"
    assert body["found"] is True
    assert body["source"] == "mathpix"


def test_scan_extract_rejects_non_image():
    user = _fake_user()
    client = TestClient(_app(user))
    image_b64 = base64.b64encode(b"fake-bytes").decode("ascii")
    with (
        patch("app.routers.math_scan.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.routers.math_scan.allow_request_fail_closed",
            AsyncMock(return_value=True),
        ),
    ):
        response = client.post(
            "/math/scan-extract",
            headers={"Authorization": "Bearer tok"},
            json={"image_base64": image_b64, "content_type": "application/pdf"},
        )
    assert response.status_code == 400


def test_scan_extract_rate_limited():
    user = _fake_user()
    client = TestClient(_app(user, Settings(math_scan_extract_per_minute=1)))
    image_b64 = base64.b64encode(b"fake-bytes").decode("ascii")
    with (
        patch("app.routers.math_scan.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.routers.math_scan.allow_request_fail_closed",
            AsyncMock(return_value=False),
        ),
    ):
        response = client.post(
            "/math/scan-extract",
            headers={"Authorization": "Bearer tok"},
            json={"image_base64": image_b64, "content_type": "image/jpeg"},
        )
    assert response.status_code == 429
