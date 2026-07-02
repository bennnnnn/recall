from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import Settings
from app.core.rest_rate_limit import _client_key
from app.main import create_app


def test_client_key_uses_user_from_bearer():
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    from app.gateways.google_auth import create_access_token

    user_id = uuid4()
    token = create_access_token(user_id, settings)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/chats",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "client": ("127.0.0.1", 1234),
    }
    request = Request(scope)
    assert _client_key(request, settings) == f"user:{user_id}"


def test_client_key_falls_back_to_ip():
    settings = Settings()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/chats",
        "headers": [],
        "client": ("10.0.0.5", 1234),
    }
    request = Request(scope)
    assert _client_key(request, settings) == "ip:10.0.0.5"


def test_middleware_skips_health_when_rate_limited():
    with (
        patch("app.core.rest_rate_limit.get_redis_client", return_value=AsyncMock()),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=False)),
    ):
        client = TestClient(create_app())
        assert client.get("/health").status_code == 200


def test_middleware_returns_429_when_over_limit():
    with (
        patch("app.core.rest_rate_limit.get_redis_client", return_value=AsyncMock()),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=False)),
    ):
        client = TestClient(create_app())
        response = client.get("/openapi.json")
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many requests. Please slow down."
