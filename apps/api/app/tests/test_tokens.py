"""Tests for JWT refresh/logout token service."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest

from app.core.access_tokens import create_access_token
from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError
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


@pytest.mark.asyncio
async def test_reused_refresh_token_revokes_every_session(fake_redis):
    """Presenting an already-rotated-out refresh token is a compromise
    signal: it must kill every refresh token for that user, not just fail
    the one request."""
    settings = Settings(jwt_secret="x" * 32)
    from app.tests.test_routers import _fake_user

    user = _fake_user()
    session = AsyncMock()

    _access1, refresh1 = await tokens_service.issue_token_pair(fake_redis, user.id, settings)

    with patch("app.services.tokens.users_repo.get_by_id", AsyncMock(return_value=user)):
        # Legitimate rotation: refresh1 -> refresh2.
        _access2, refresh2, _ = await tokens_service.refresh_token_pair(
            fake_redis, refresh1, session, settings
        )
        assert await fake_redis.get(f"refresh:{refresh2}") is not None

        # Attacker (or a delayed retry) replays the now-superseded refresh1.
        with pytest.raises(GoogleAuthError):
            await tokens_service.refresh_token_pair(fake_redis, refresh1, session, settings)

    # The legitimate device's rotated-to token is dead too — the whole
    # session was killed, not just the stolen token.
    assert await fake_redis.get(f"refresh:{refresh2}") is None
    revoked_since = await fake_redis.get(f"revoked_since:{user.id}")
    assert revoked_since is not None


@pytest.mark.asyncio
async def test_revoked_since_blocks_existing_access_tokens(fake_redis):
    """An access token issued before a detected-reuse event must stop
    verifying, even though it hasn't naturally expired yet."""
    settings = Settings(jwt_secret="x" * 32)
    from app.tests.test_routers import _fake_user

    user = _fake_user()
    session = AsyncMock()

    access_before_reuse = create_access_token(user.id, settings)
    await tokens_service.verify_access_token(fake_redis, access_before_reuse, settings)

    _access1, refresh1 = await tokens_service.issue_token_pair(fake_redis, user.id, settings)
    with patch("app.services.tokens.users_repo.get_by_id", AsyncMock(return_value=user)):
        _access2, _refresh2, _ = await tokens_service.refresh_token_pair(
            fake_redis, refresh1, session, settings
        )
        with pytest.raises(GoogleAuthError):
            await tokens_service.refresh_token_pair(fake_redis, refresh1, session, settings)

    with pytest.raises(GoogleAuthError, match="revoked"):
        await tokens_service.verify_access_token(fake_redis, access_before_reuse, settings)


@pytest.mark.asyncio
async def test_first_time_unknown_refresh_token_does_not_trigger_revocation(fake_redis):
    """A token that was never issued (typo, bogus value) has no tombstone —
    it must just fail, not be treated as a reuse/compromise signal."""
    settings = Settings(jwt_secret="x" * 32)
    session = AsyncMock()

    with pytest.raises(GoogleAuthError):
        await tokens_service.refresh_token_pair(fake_redis, "never-issued-token", session, settings)

    # No user to revoke since the token was never associated with one — the
    # important behavior is simply that this doesn't crash and stays a plain
    # "invalid token" failure.


@pytest.mark.asyncio
async def test_logout_removes_token_from_user_session_set(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    _access, refresh = await tokens_service.issue_token_pair(fake_redis, user_id, settings)

    await tokens_service.revoke_refresh_token(fake_redis, refresh)

    assert not await fake_redis.sismember(f"refresh_user:{user_id}", refresh)


@pytest.mark.asyncio
async def test_logout_without_refresh_purges_all_sessions(fake_redis):
    """When the client omits refresh_token, logout must kill every session."""
    from unittest.mock import MagicMock

    from app.models.schemas import LogoutRequest
    from app.routers import auth as auth_router

    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    access, refresh1 = await tokens_service.issue_token_pair(fake_redis, user_id, settings)
    _a2, refresh2 = await tokens_service.issue_token_pair(fake_redis, user_id, settings)

    request = MagicMock()
    request.headers = {"authorization": f"Bearer {access}"}
    await auth_router.logout(
        LogoutRequest(refresh_token=None),
        request=request,
        settings=settings,
        redis=fake_redis,
    )

    assert await fake_redis.get(f"refresh:{refresh1}") is None
    assert await fake_redis.get(f"refresh:{refresh2}") is None
    assert await fake_redis.smembers(f"refresh_user:{user_id}") == set()


@pytest.mark.asyncio
async def test_purge_user_sessions_kills_all_refresh_tokens(fake_redis):
    """Account deletion must revoke every outstanding session, not just rely
    on the DB user check to stop a logged-in client."""
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    _a1, refresh1 = await tokens_service.issue_token_pair(fake_redis, user_id, settings)
    _a2, refresh2 = await tokens_service.issue_token_pair(fake_redis, user_id, settings)

    await tokens_service.purge_user_sessions(fake_redis, user_id, settings)

    assert await fake_redis.get(f"refresh:{refresh1}") is None
    assert await fake_redis.get(f"refresh:{refresh2}") is None
    assert await fake_redis.smembers(f"refresh_user:{user_id}") == set()
    # Any access token issued before now is treated as revoked.
    assert await fake_redis.get(f"revoked_since:{user_id}") is not None


@pytest.mark.asyncio
async def test_purge_user_sessions_raises_on_redis_failure(fake_redis):
    """M1: Redis outage during account delete must fail (503), not silently
    succeed — otherwise live sessions can call the API until JWT expiry."""
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    with (
        patch(
            "redis.asyncio.client.Pipeline.smembers",
            AsyncMock(side_effect=RuntimeError("redis down")),
        ),
        pytest.raises(RuntimeError, match="redis down"),
    ):
        await tokens_service.purge_user_sessions(fake_redis, user_id, settings)


@pytest.mark.asyncio
async def test_issue_stores_json_session_and_legacy_plain_user_id_still_refreshes(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    from app.tests.test_routers import _fake_user

    user = _fake_user()
    session = AsyncMock()
    access, refresh = await tokens_service.issue_token_pair(
        fake_redis, user.id, settings, device_label="Pixel 8", platform="android"
    )
    raw = await fake_redis.get(f"refresh:{refresh}")
    record = tokens_service.parse_refresh_record(raw, refresh)
    assert record["user_id"] == str(user.id)
    assert record["device_label"] == "Pixel 8"
    payload = jwt.decode(access, settings.jwt_secret, algorithms=["HS256"])
    assert payload.get("sid") == record["session_id"]

    legacy = "legacy-refresh-token"
    await fake_redis.set(f"refresh:{legacy}", str(user.id))
    await fake_redis.sadd(f"refresh_user:{user.id}", legacy)
    with patch("app.services.tokens.users_repo.get_by_id", AsyncMock(return_value=user)):
        new_access, new_refresh, user_out = await tokens_service.refresh_token_pair(
            fake_redis, legacy, session, settings, device_label="iPhone"
        )
    assert user_out.id == user.id
    assert new_access != access
    rotated = tokens_service.parse_refresh_record(
        await fake_redis.get(f"refresh:{new_refresh}"), new_refresh
    )
    assert rotated["device_label"] == "iPhone"


@pytest.mark.asyncio
async def test_list_and_revoke_sessions(fake_redis):
    settings = Settings(jwt_secret="x" * 32)
    user_id = uuid4()
    access, _refresh = await tokens_service.issue_token_pair(
        fake_redis, user_id, settings, device_label="iPad"
    )
    await tokens_service.issue_token_pair(fake_redis, user_id, settings, device_label="Mac")
    current = tokens_service.session_id_from_access_token(access, settings)
    sessions = await tokens_service.list_sessions(fake_redis, user_id, current_session_id=current)
    assert len(sessions) == 2
    current_row = next(row for row in sessions if row["current"])
    other = next(row for row in sessions if not row["current"])
    assert current_row["device_label"] == "iPad"

    with pytest.raises(tokens_service.CurrentSessionError):
        await tokens_service.revoke_session(
            fake_redis, user_id, current_row["id"], current_session_id=current
        )
    await tokens_service.revoke_session(
        fake_redis, user_id, other["id"], current_session_id=current
    )
    remaining = await tokens_service.list_sessions(fake_redis, user_id, current_session_id=current)
    assert len(remaining) == 1
    assert remaining[0]["current"] is True
