"""Redis outage → RedisUnavailableError (fail closed, 503 / unavailable)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import deps
from app.core.access_tokens import create_access_token
from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.services import quota as quota_service
from app.services import tokens as tokens_service
from app.services.chat.stream_events import error_payload_for_exception


@pytest.mark.asyncio
async def test_reserve_usage_raises_when_redis_down():
    redis = AsyncMock()
    redis.incrby = AsyncMock(side_effect=RedisConnectionError("down"))
    with pytest.raises(RedisUnavailableError):
        await quota_service.reserve_usage(redis, "u1", 100, daily_limit=1000)


@pytest.mark.asyncio
async def test_verify_access_token_raises_when_redis_down():
    settings = Settings(jwt_secret="x" * 32)
    token = create_access_token(uuid4(), settings)
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=RedisConnectionError("down"))
    with pytest.raises(RedisUnavailableError):
        await tokens_service.verify_access_token(redis, token, settings)


@pytest.mark.asyncio
async def test_get_current_user_maps_redis_outage_to_503():
    settings = Settings(jwt_secret="test-secret-32-chars-long-enough!!")
    credentials = MagicMock()
    credentials.credentials = "tok"
    with patch(
        "app.core.deps.tokens_service.verify_access_token",
        AsyncMock(side_effect=RedisUnavailableError()),
    ):
        with pytest.raises(HTTPException) as exc:
            await deps.get_current_user(
                credentials=credentials,
                session=AsyncMock(),
                settings=settings,
                redis=AsyncMock(),
            )
    assert exc.value.status_code == 503
    assert exc.value.headers is not None
    assert exc.value.headers.get("Retry-After") == "5"


def test_error_payload_for_redis_unavailable():
    payload = error_payload_for_exception(RedisUnavailableError())
    assert payload["type"] == "error"
    assert payload["code"] == "unavailable"
