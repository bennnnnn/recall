from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import Settings
from app.core.rest_rate_limit import _client_key
from app.main import create_app


def test_client_key_uses_user_from_bearer():
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    from app.core.access_tokens import create_access_token

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


def test_middleware_skips_when_limit_disabled():
    with patch("app.core.config.get_settings", return_value=Settings(rest_rate_limit_per_minute=0)):
        client = TestClient(create_app())
        assert client.get("/openapi.json").status_code == 200


def test_middleware_fails_closed_when_redis_check_fails():
    # A Redis outage must not let the rate limiter silently disappear — that
    # would expose every protected endpoint to unbounded traffic. Fail closed
    # with 429 + Retry-After so clients back off and the limit re-engages.
    broken = AsyncMock()
    broken.incr = AsyncMock(side_effect=RuntimeError("redis down"))
    with patch("app.core.rest_rate_limit.get_redis_client", return_value=broken):
        client = TestClient(create_app())
        response = client.get("/openapi.json")
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit unavailable. Please retry shortly."
    assert response.headers.get("retry-after") == "5"


def test_client_key_falls_back_to_ip_on_invalid_bearer():
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/chats",
        "headers": [(b"authorization", b"Bearer not-a-jwt")],
        "client": ("10.0.0.5", 1234),
    }
    request = Request(scope)
    assert _client_key(request, settings) == "ip:10.0.0.5"
