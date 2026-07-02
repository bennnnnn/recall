"""Tests for JWT refresh/logout token service."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError, create_access_token
from app.services import tokens as tokens_service


@pytest.mark.asyncio
async def test_issue_and_refresh_token_pair(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    from app.tests.test_routers import _fake_user

    user = _fake_user()
    session = AsyncMock()
    access, refresh = await tokens_service.issue_token_pair(fake_redis, user.id, settings)

    with patch("app.services.tokens.users_repo.get_by_id", AsyncMock(return_value=user)):
        new_access, new_refresh, user_out = await tokens_service.refresh_token_pair(
            fake_redis, refresh, session, settings
        )

    assert new_access != access
    assert new_refresh != refresh
    assert user_out.id == user.id


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_token(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    session = AsyncMock()

    with pytest.raises(GoogleAuthError):
        await tokens_service.refresh_token_pair(
            fake_redis, "not-a-real-refresh-token", session, settings
        )


@pytest.mark.asyncio
async def test_revoke_access_token_blocks_verify(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    token = create_access_token(user_id, settings)
    await tokens_service.verify_access_token(fake_redis, token, settings)

    await tokens_service.revoke_access_token(fake_redis, token, settings)
    with pytest.raises(GoogleAuthError, match="revoked"):
        await tokens_service.verify_access_token(fake_redis, token, settings)


@pytest.mark.asyncio
async def test_revoke_refresh_token(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    _access, refresh = await tokens_service.issue_token_pair(fake_redis, user_id, settings)
    await tokens_service.revoke_refresh_token(fake_redis, refresh)
    assert await fake_redis.get(f"refresh:{refresh}") is None
