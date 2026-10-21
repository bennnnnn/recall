"""Every request's token check reads its revocation keys in one Redis round trip.

The token, its signed-in device and the user's revoked-since cutoff were three
GETs, one after another, before every authenticated request and every chat frame.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import access_tokens
from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError

_SETTINGS = Settings(jwt_secret="x" * 32)


def _commands(redis: Any) -> list[str]:
    """Record the name of every command ``redis`` sends from here on."""
    sent: list[str] = []
    execute = redis.execute_command

    async def recording(*args: Any, **kwargs: Any) -> Any:
        sent.append(str(args[0]).upper())
        return await execute(*args, **kwargs)

    redis.execute_command = recording
    return sent


def _token(*, session_id: str | None = "device-1") -> tuple[str, dict[str, Any]]:
    token = access_tokens.create_access_token(uuid4(), _SETTINGS, session_id=session_id)
    return token, jwt.decode(token, _SETTINGS.jwt_secret, algorithms=["HS256"])


async def _revoke_token(redis: Any, claims: dict[str, Any]) -> None:
    await redis.set(access_tokens.revoked_key(claims["jti"]), "1")


async def _revoke_device(redis: Any, claims: dict[str, Any]) -> None:
    await redis.set(access_tokens.revoked_session_key(claims["sid"]), "1")


async def _revoke_since_now(redis: Any, claims: dict[str, Any]) -> None:
    await redis.set(access_tokens.revoked_since_key(claims["sub"]), str(time.time() + 1))


@pytest.mark.parametrize("revoke", [_revoke_token, _revoke_device, _revoke_since_now])
async def test_verify_access_token_refuses_each_revocation_in_one_round_trip(
    fake_redis, revoke: Callable[[Any, dict[str, Any]], Awaitable[None]]
) -> None:
    token, claims = _token()
    await revoke(fake_redis, claims)
    sent = _commands(fake_redis)

    with pytest.raises(GoogleAuthError, match="revoked"):
        await access_tokens.verify_access_token(fake_redis, token, _SETTINGS)

    assert sent == ["MGET"]


@pytest.mark.parametrize("session_id", ["device-1", None])
async def test_verify_access_token_passes_a_live_token_in_one_round_trip(
    fake_redis, session_id: str | None
) -> None:
    token, claims = _token(session_id=session_id)
    # A cutoff from before this token was issued (an earlier sign-out) leaves it valid.
    await fake_redis.set(access_tokens.revoked_since_key(claims["sub"]), str(claims["iat"] - 60))
    sent = _commands(fake_redis)

    user_id = await access_tokens.verify_access_token(fake_redis, token, _SETTINGS)

    assert str(user_id) == claims["sub"]
    assert sent == ["MGET"]


async def test_verify_access_token_fails_closed_when_redis_is_down() -> None:
    token, _claims = _token()
    redis = AsyncMock()
    redis.mget.side_effect = RedisConnectionError("down")

    with pytest.raises(RedisUnavailableError):
        await access_tokens.verify_access_token(redis, token, _SETTINGS)


async def test_verify_access_token_refuses_a_bad_signature_without_redis() -> None:
    token = access_tokens.create_access_token(uuid4(), Settings(jwt_secret="y" * 32))
    redis = AsyncMock()

    with pytest.raises(GoogleAuthError, match="Invalid"):
        await access_tokens.verify_access_token(redis, token, _SETTINGS)

    assert redis.mock_calls == []
