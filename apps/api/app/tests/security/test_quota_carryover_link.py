"""A sign-in identity linked to an existing account by email brings its carried counters.

Account delete keeps the day's counters per sign-in identity (``quota_carryover``), and a
new account for that identity is raised to them. An identity can also come back by joining
an account that already holds its email (``service.login_with_*``, ``email_authority``):
delete an Apple account, sign in with Google on the same address, then with Apple. That
link applied nothing, so the deleted account's day started again from zero.

Real Postgres and the configured Redis (``real_redis``), through the HTTP sign-in routes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionLocal, engine
from app.core.redis import get_redis_client
from app.models.orm import User
from app.modules.account import quota_carryover, signin_limit
from app.modules.account.email_authority import SignInProvider
from app.modules.billing.entitlements import setting_name
from app.services import quota
from app.services.quota import carryover, counters, live_talk

from .conftest import delete_accounts, isolated_settings, reset_process_caches

# The deleted account's day, and the account it comes back to: each counter either side
# used more of, plus counters only one side used.
_DELETED = {"usage": 1234, "imggen": 2, "tavily": 4}
_LIVE_TALK_SECONDS = 300
_SURVIVOR = {"usage": 5000, "tavily": 1}
# Raise-only on each counter (``carryover.apply_carried_usage``): the larger of the two.
_MERGED = {"usage": 5000, "imggen": 2, "tavily": 4}
_EMAILS = {"apple": "icloud.com", "google": "gmail.com"}  # where that provider owns the address


@dataclass
class Linked:
    client: httpx.AsyncClient
    settings: Settings
    redis: Any
    users: list[UUID]
    # What the test made in Redis, deleted by name after it: the configured Redis may be a
    # shared development one, so nothing else (the job stream, the per-IP limiter) is touched.
    made_ids: set[UUID] = field(default_factory=set)
    identities: set[tuple[str, str]] = field(default_factory=set)
    refresh_tokens: set[str] = field(default_factory=set)


@pytest.fixture
async def linked(
    real_redis: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[Linked]:
    """The app on the configured Redis; the keys of the test's accounts and identities are
    deleted after it."""
    from app.main import create_app

    settings = isolated_settings(monkeypatch, tmp_path)
    # One UTC day and month for the whole test: a run across midnight keeps its counters.
    day, month = quota.utc_today(), quota.utc_month()
    monkeypatch.setattr(counters, "clock", lambda: day)
    monkeypatch.setattr(live_talk, "utc_month", lambda: month)
    monkeypatch.setattr(carryover, "utc_month", lambda: month)
    redis = get_redis_client()
    await engine.dispose(close=False)
    world: Linked | None = None
    try:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            world = Linked(client=client, settings=settings, redis=redis, users=[])
            yield world
    finally:
        if world is not None:
            await delete_accounts(*world.users)
            await _delete_made_keys(world)
        await redis.aclose()
        await engine.dispose(close=False)
        reset_process_caches()


async def _delete_made_keys(world: Linked) -> None:
    made = {f"refresh:{token}" for token in world.refresh_tokens}
    for provider, sub in world.identities:
        made.add(quota_carryover.carry_key(world.settings, provider, sub))
        limited: SignInProvider = "apple" if provider == "apple" else "google"
        made.add(signin_limit.identity_key(world.settings, limited, sub))
    for user_id in world.made_ids:
        made.update([key async for key in world.redis.scan_iter(match=f"*{user_id}*")])
    if made:
        await world.redis.delete(*made)


async def _sign_in(world: Linked, provider: str, sub: str, email: str) -> httpx.Response:
    world.identities.add((provider, sub))
    payload: dict[str, Any] = {"sub": sub, "email": email, "email_verified": True}
    if provider == "apple":
        payload["email_verified"] = "true"
    verify = f"app.modules.account.service.verify_{provider}_id_token"
    with patch(verify, AsyncMock(return_value=payload)):
        return await world.client.post(
            f"/auth/{provider}", json={"id_token": "token", "nonce": "n"}
        )


async def _signed_in(world: Linked, provider: str, sub: str, email: str) -> tuple[UUID, str]:
    response = await _sign_in(world, provider, sub, email)
    assert response.status_code == 200, response.text
    body = response.json()
    user_id = UUID(body["user"]["id"])
    world.made_ids.add(user_id)
    world.refresh_tokens.add(str(body["refresh_token"]))
    if user_id not in world.users:
        world.users.append(user_id)
    return user_id, str(body["access_token"])


async def _use(redis: Any, user_id: UUID, used: dict[str, int], live_talk: int = 0) -> None:
    allowances: dict[str, Any] = {
        setting_name(spec.allowance, "pro"): 10 for spec in counters.COUNTERS.values()
    }
    caps = Settings(**allowances)
    user = User(id=user_id, plan="pro")
    tokens = used["usage"]
    assert await quota.reserve_usage_up_to(redis, str(user_id), tokens, daily_limit=10**9) == tokens
    for name, spec in counters.COUNTERS.items():
        for _ in range(used.get(spec.prefix, 0)):
            assert await counters.reserve(name, redis, user, caps)
    if live_talk:
        granted = await quota.reserve_live_talk_seconds(
            redis,
            user_id,
            allowance_seconds=3600,
            max_session_seconds=live_talk,
            min_session_seconds=1,
        )
        assert granted == live_talk


async def _counts(redis: Any, user_id: UUID) -> dict[str, int]:
    day = quota.utc_today()
    counts = {
        prefix: int(await redis.get(counters.daily_key(prefix, user_id, day)) or 0)
        for prefix in ("usage", "imggen", "tavily")
    }
    return {prefix: used for prefix, used in counts.items() if used}


async def _delete(world: Linked, user_id: UUID, token: str) -> None:
    from app.background.handlers import _handle_storage_sweep

    response = await world.client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204, response.text
    await _handle_storage_sweep(world.settings, {"user_id": str(user_id)})
    world.users.remove(user_id)


async def _linked_sub(user_id: UUID, provider: str) -> str | None:
    column = User.apple_sub if provider == "apple" else User.google_sub
    async with SessionLocal() as session:
        value = (await session.execute(select(column).where(User.id == user_id))).scalar()
    return str(value) if value else None


async def _deleted_then_other_account(world: Linked, deleted: str) -> tuple[str, str, UUID]:
    """An account made with *deleted*'s provider uses its day and is deleted; the same
    address then gets an account through the other provider, which uses some of its own.
    Returns the deleted identity's sub, the address, and the surviving account."""
    other = "google" if deleted == "apple" else "apple"
    sub, email = f"{deleted}-{uuid4()}", f"link-{uuid4().hex[:12]}@{_EMAILS[deleted]}"
    first, token = await _signed_in(world, deleted, sub, email)
    await _use(world.redis, first, _DELETED, live_talk=_LIVE_TALK_SECONDS)
    await _delete(world, first, token)
    assert await world.redis.get(quota_carryover.carry_key(world.settings, deleted, sub))

    survivor, _ = await _signed_in(world, other, f"{other}-{uuid4()}", email)
    assert survivor != first
    await _use(world.redis, survivor, _SURVIVOR)
    assert await _counts(world.redis, survivor) == _SURVIVOR
    return sub, email, survivor


@pytest.mark.asyncio
@pytest.mark.parametrize("deleted", ["apple", "google"])
async def test_quota_carryover_linked_identity_raises_the_account_once(
    linked: Linked, deleted: str
) -> None:
    sub, email, survivor = await _deleted_then_other_account(linked, deleted)
    applied = AsyncMock(wraps=quota.apply_carried_usage)

    with patch("app.services.quota.apply_carried_usage", applied):
        joined, _ = await _signed_in(linked, deleted, sub, email)
        assert joined == survivor
        assert await _linked_sub(survivor, deleted) == sub
        assert await _counts(linked.redis, survivor) == _MERGED
        assert await quota.live_talk_used_seconds(linked.redis, survivor) == _LIVE_TALK_SECONDS
        # Used: the snapshot is gone.
        assert (
            await linked.redis.get(quota_carryover.carry_key(linked.settings, deleted, sub)) is None
        )

        # The next sign-in finds the identity on the account and applies nothing again.
        again, _ = await _signed_in(linked, deleted, sub, email)
        assert again == survivor
    assert applied.await_count == 1
    assert await _counts(linked.redis, survivor) == _MERGED


@pytest.mark.asyncio
async def test_quota_carryover_unrestored_link_refuses_sign_in_and_links_nothing(
    linked: Linked,
) -> None:
    """A link whose carried counters cannot be applied is not saved, as with a new account:
    503 ``sign_in_unavailable``, the identity not on the account, the snapshot kept, and the
    retry links and restores."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    sub, email, survivor = await _deleted_then_other_account(linked, "apple")
    key = quota_carryover.carry_key(linked.settings, "apple", sub)
    snapshot = await linked.redis.get(key)

    down = AsyncMock(side_effect=RedisConnectionError("Error 111 connecting to redis"))
    with patch("app.services.quota.apply_carried_usage", down):
        refused = await _sign_in(linked, "apple", sub, email)

    assert refused.status_code == 503, refused.text
    assert refused.json()["detail"]["code"] == "sign_in_unavailable"
    assert await _linked_sub(survivor, "apple") is None
    assert await linked.redis.get(key) == snapshot
    assert await _counts(linked.redis, survivor) == _SURVIVOR

    joined, _ = await _signed_in(linked, "apple", sub, email)
    assert joined == survivor
    assert await _counts(linked.redis, survivor) == _MERGED
    assert await linked.redis.get(key) is None
