"""Sessions end whole, only their own account ends them, and every input stays bounded.

Low findings of the 2026-11-26 security review: sign-out revoked the presented access
token but not its session; a session id was revoked before it was checked against the
caller's account; an account kept any number of sessions; refresh and ID tokens of any
length reached Redis or the verifier; plan syncs had no limit.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.access_tokens import create_access_token
from app.core.config import Settings
from app.exceptions import AuthenticationError, RateLimitedError
from app.models.schemas import AppleAuthRequest, GoogleAuthRequest, LogoutRequest, RefreshRequest
from app.models.schemas.auth import ID_TOKEN_MAX_CHARS, REFRESH_TOKEN_MAX_CHARS
from app.modules.account import api as account_api
from app.modules.account import lifecycle
from app.modules.account import tokens as tokens_service
from app.tests.api_support import api_user

_SETTINGS = Settings(jwt_secret="x" * 32)


async def _refreshed(redis: Any, refresh: str) -> tuple[str, str]:
    user = api_user()
    with patch("app.modules.account.tokens.users_repo.get_by_id", AsyncMock(return_value=user)):
        access, new_refresh, _ = await tokens_service.refresh_token_pair(
            redis, refresh, AsyncMock(), _SETTINGS
        )
    return access, new_refresh


@pytest.mark.parametrize("presented", ["both", "refresh only", "access only"])
async def test_sign_out_ends_the_session_with_every_access_token_it_issued(
    fake_redis: Any, presented: str
) -> None:
    """An access token issued before the last refresh still worked after sign-out."""
    user_id = uuid4()
    earlier_access, refresh = await tokens_service.issue_token_pair(fake_redis, user_id, _SETTINGS)
    access, refresh = await _refreshed(fake_redis, refresh)
    other_access, _ = await tokens_service.issue_token_pair(fake_redis, user_id, _SETTINGS)

    await lifecycle.logout(
        AsyncMock(),
        fake_redis,
        _SETTINGS,
        access_token=None if presented == "refresh only" else access,
        refresh_token=None if presented == "access only" else refresh,
    )

    for token in (earlier_access, access):
        with pytest.raises(AuthenticationError):
            await tokens_service.verify_access_token(fake_redis, token, _SETTINGS)
    assert await tokens_service.refresh_token_user(fake_redis, refresh) is None
    # Another device of the account stays signed in.
    assert await tokens_service.verify_access_token(fake_redis, other_access, _SETTINGS) == user_id


async def test_another_accounts_session_id_revokes_nothing(fake_redis: Any) -> None:
    """The revocation was written before the id was looked up in the caller's account, so a
    caller who learned another account's session id signed that device out."""
    mine, victim = uuid4(), uuid4()
    my_access, _ = await tokens_service.issue_token_pair(fake_redis, mine, _SETTINGS)
    their_access, their_refresh = await tokens_service.issue_token_pair(
        fake_redis, victim, _SETTINGS
    )
    their_session = tokens_service.session_id_from_access_token(their_access, _SETTINGS)
    assert their_session is not None

    with pytest.raises(tokens_service.SessionNotFoundError):
        await tokens_service.revoke_session(
            fake_redis,
            mine,
            their_session,
            current_session_id=tokens_service.session_id_from_access_token(my_access, _SETTINGS),
            settings=_SETTINGS,
        )

    assert await fake_redis.get(f"revoked:sid:{their_session}") is None
    assert await tokens_service.verify_access_token(fake_redis, their_access, _SETTINGS) == victim
    assert await tokens_service.refresh_token_user(fake_redis, their_refresh) == victim


async def test_a_sign_in_past_the_cap_ends_the_least_recently_used_session(
    fake_redis: Any,
) -> None:
    user_id = uuid4()
    cap = tokens_service.MAX_SESSIONS_PER_ACCOUNT
    pairs = [await tokens_service.issue_token_pair(fake_redis, user_id, _SETTINGS)]
    pairs += [
        await tokens_service.issue_token_pair(fake_redis, user_id, _SETTINGS) for _ in range(cap)
    ]

    sessions = await tokens_service.list_sessions(fake_redis, user_id, current_session_id=None)
    assert len(sessions) == cap
    assert await fake_redis.scard(f"refresh_user:{user_id}") == cap
    oldest_access, oldest_refresh = pairs[0]
    with pytest.raises(AuthenticationError):
        await tokens_service.verify_access_token(fake_redis, oldest_access, _SETTINGS)
    assert await tokens_service.refresh_token_user(fake_redis, oldest_refresh) is None
    newest_access, _ = pairs[-1]
    assert await tokens_service.verify_access_token(fake_redis, newest_access, _SETTINGS) == user_id


async def _seed_sessions(redis: Any, user_id: Any, count: int) -> list[str]:
    """Sessions an account from before the cap holds, oldest first: their ids."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    ids: list[str] = []
    for n in range(count):
        session_id, token = str(uuid4()), f"seeded-{n}-{uuid4().hex}"
        seen = (start + timedelta(minutes=n)).isoformat()
        record = {"user_id": str(user_id), "session_id": session_id, "created_at": seen,
                  "last_seen_at": seen, "device_label": f"device {n}", "platform": "ios"}  # fmt: skip
        await redis.set(f"refresh:{token}", json.dumps(record), ex=3600)
        await redis.sadd(f"refresh_user:{user_id}", token)
        ids.append(session_id)
    return ids


async def test_an_account_far_past_the_cap_is_trimmed_in_one_round_trip(fake_redis: Any) -> None:
    """1,000 sessions from a sign-in loop used to end one at a time inside the sign-in."""
    user_id = uuid4()
    seeded = await _seed_sessions(fake_redis, user_id, 300)
    pipelines = MagicMock(wraps=fake_redis.pipeline)
    writes = MagicMock(wraps=fake_redis.set)
    with patch.object(fake_redis, "pipeline", pipelines), patch.object(fake_redis, "set", writes):
        access, _ = await tokens_service.issue_token_pair(fake_redis, user_id, _SETTINGS)

    cap = tokens_service.MAX_SESSIONS_PER_ACCOUNT
    assert await fake_redis.scard(f"refresh_user:{user_id}") == cap
    # Expired-member check, the trim, the new session: never one call per session.
    assert pipelines.call_count <= 3
    writes.assert_not_called()
    assert await fake_redis.get(f"revoked:sid:{seeded[0]}") == "1"
    assert await fake_redis.get(f"revoked:sid:{seeded[-1]}") is None
    assert await tokens_service.verify_access_token(fake_redis, access, _SETTINGS) == user_id


async def test_the_session_route_lists_the_cap_with_this_device_among_them(
    fake_redis: Any,
) -> None:
    """GET /auth/sessions for an account past the cap, this device the least recently seen."""
    from starlette.requests import Request

    user = api_user()
    seeded = await _seed_sessions(fake_redis, user.id, tokens_service.MAX_SESSIONS_PER_ACCOUNT + 5)
    mine = create_access_token(user.id, _SETTINGS, session_id=seeded[0])
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/sessions",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {mine}".encode())],
        }
    )

    response = await account_api.list_sessions(
        request, user=user, settings=_SETTINGS, redis=fake_redis
    )

    rows = json.loads(bytes(response.body))["sessions"]
    assert len(rows) == tokens_service.MAX_SESSIONS_PER_ACCOUNT
    assert [row["id"] for row in rows if row["current"]] == [seeded[0]]
    assert rows[0]["id"] == seeded[-1]


def test_the_session_list_is_bounded_and_keeps_this_device() -> None:
    cap = tokens_service.MAX_SESSIONS_PER_ACCOUNT
    rows: list[dict[str, Any]] = [{"id": str(n), "current": False} for n in range(cap + 5)]
    rows[-1]["current"] = True

    listed = account_api._listed_sessions(rows)

    assert len(listed) == cap
    assert listed[-1]["id"] == str(cap + 4)
    assert [row["id"] for row in listed[:-1]] == [str(n) for n in range(cap - 1)]
    assert account_api._listed_sessions(rows[:3]) == rows[:3]


def test_token_strings_are_bounded_at_the_schema() -> None:
    long_refresh = "r" * (REFRESH_TOKEN_MAX_CHARS + 1)
    long_id_token = "i" * (ID_TOKEN_MAX_CHARS + 1)
    for model, field, value in (
        (RefreshRequest, "refresh_token", long_refresh),
        (LogoutRequest, "refresh_token", long_refresh),
        (GoogleAuthRequest, "id_token", long_id_token),
        (AppleAuthRequest, "id_token", long_id_token),
    ):
        with pytest.raises(ValidationError):
            model.model_validate({field: value})
    assert RefreshRequest(refresh_token="r" * 43).refresh_token == "r" * 43


async def test_an_overlong_refresh_token_never_becomes_a_redis_key() -> None:
    """The web's cookie skips the request schema: the token service refuses it without a
    Redis call."""
    long_refresh = "r" * (REFRESH_TOKEN_MAX_CHARS + 1)
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=AssertionError("read a Redis key"))
    redis.pipeline = MagicMock(side_effect=AssertionError("wrote a Redis key"))
    with pytest.raises(AuthenticationError):
        await tokens_service.refresh_token_pair(redis, long_refresh, AsyncMock(), _SETTINGS)
    assert await tokens_service.refresh_token_user(redis, long_refresh) is None
    await tokens_service.revoke_refresh_token(redis, long_refresh)


async def test_plan_syncs_are_limited_per_account(fake_redis: Any) -> None:
    """Each sync is a RevenueCat REST call: a client in a loop stops at the minute's limit."""
    user = api_user(plan="pro")
    settings = Settings(jwt_secret="x" * 32, revenuecat_secret_key="sk_test")
    with patch.object(
        account_api.subscription_service,
        "sync_user_plan_from_revenuecat",
        AsyncMock(return_value=user),
    ) as sync:
        for _ in range(account_api._SUBSCRIPTION_SYNCS_PER_MINUTE):
            await account_api.sync_subscription(
                user=user, session=AsyncMock(), settings=settings, redis=fake_redis
            )
        with pytest.raises(RateLimitedError):
            await account_api.sync_subscription(
                user=user, session=AsyncMock(), settings=settings, redis=fake_redis
            )
        # Another account keeps its own allowance.
        await account_api.sync_subscription(
            user=api_user(plan="pro"), session=AsyncMock(), settings=settings, redis=fake_redis
        )
    assert sync.await_count == account_api._SUBSCRIPTION_SYNCS_PER_MINUTE + 1


async def test_plan_syncs_stop_at_the_hours_limit_across_minutes(fake_redis: Any) -> None:
    """Ten a minute, every minute, still stops at sixty an hour."""
    user = api_user(plan="pro")
    settings = Settings(jwt_secret="x" * 32, revenuecat_secret_key="sk_test")
    per_minute = account_api._SUBSCRIPTION_SYNCS_PER_MINUTE
    per_hour = account_api._SUBSCRIPTION_SYNCS_PER_HOUR
    with patch.object(
        account_api.subscription_service,
        "sync_user_plan_from_revenuecat",
        AsyncMock(return_value=user),
    ):
        for n in range(per_hour):
            if n % per_minute == 0:
                # A new minute: its own window starts empty, the hour's keeps counting.
                await fake_redis.delete(f"rate:billing_sync:min:{user.id}")
            await account_api.sync_subscription(
                user=user, session=AsyncMock(), settings=settings, redis=fake_redis
            )
        await fake_redis.delete(f"rate:billing_sync:min:{user.id}")
        with pytest.raises(RateLimitedError) as refused:
            await account_api.sync_subscription(
                user=user, session=AsyncMock(), settings=settings, redis=fake_redis
            )
    assert refused.value.headers == {"Retry-After": "3600"}
