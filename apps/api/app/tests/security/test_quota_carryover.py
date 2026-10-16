"""Deleting an account and signing up again with the same login keeps today's limits.

Quota counters are keyed by user id, so a new account would start every daily
cap (and this month's live talk minutes) from zero. Account delete keeps one
snapshot keyed by an HMAC of the Google/Apple identity; the new account for the
same identity picks it up at sign-up.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import User
from app.modules.billing.entitlements import setting_name
from app.services import quota
from app.services.quota import counters

from .conftest import World, delete_accounts

# Every per-user daily counter, named independently of the code under test.
DAILY_PREFIXES = ("usage", "imgup", "speech", "tts", "tavily", "imggen", "imgsearch")


def _pro_caps(cap: int) -> Settings:
    caps: dict[str, Any] = {
        setting_name(spec.allowance, "pro"): cap for spec in counters.COUNTERS.values()
    }
    return Settings(**caps)


async def _google_sub(user_id: UUID) -> str:
    async with SessionLocal() as session:
        sub = (await session.execute(select(User.google_sub).where(User.id == user_id))).scalar()
    assert sub
    return str(sub)


async def _sign_in_google(world: World, *, sub: str, email: str) -> UUID:
    payload = {"sub": sub, "email": email, "name": "Again", "email_verified": True}
    with patch(
        "app.modules.account.service.verify_google_id_token", AsyncMock(return_value=payload)
    ):
        response = await world.client.post("/auth/google", json={"id_token": "token"})
    assert response.status_code == 200, response.text
    return UUID(response.json()["user"]["id"])


async def _use_quota(redis: Any, user_id: UUID) -> None:
    """What a busy day leaves: tokens, uploads, voice, searches, images, live talk."""
    assert await quota.reserve_usage(redis, str(user_id), 1234, daily_limit=10**9)
    user, caps = User(id=user_id, plan="pro"), _pro_caps(10)
    for _ in range(2):
        assert await counters.reserve("image_upload", redis, user, caps)
    for _ in range(3):
        assert await counters.reserve("speech_transcription", redis, user, caps)
    assert await counters.reserve("speech_tts", redis, user, caps)
    for _ in range(4):
        assert await counters.reserve("tavily_search", redis, user, caps)
    assert await counters.reserve("image_generation", redis, user, caps)
    for _ in range(2):
        assert await counters.reserve("image_search", redis, user, caps)
    granted = await quota.reserve_live_talk_seconds(
        redis,
        user_id,
        allowance_seconds=3600,
        max_session_seconds=300,
        min_session_seconds=1,
    )
    assert granted == 300


_USED = {
    "usage": 1234,
    "imgup": 2,
    "speech": 3,
    "tts": 1,
    "tavily": 4,
    "imggen": 1,
    "imgsearch": 2,
}


async def _daily_counts(redis: Any, user_id: UUID, day: Any = None) -> dict[str, int]:
    day = day or quota.utc_today()
    return {
        prefix: int(await redis.get(counters.daily_key(prefix, user_id, day)) or 0)
        for prefix in DAILY_PREFIXES
    }


async def _delete_and_sweep(world: World, user_id: UUID, headers: dict[str, str]) -> None:
    from app.background.handlers import _handle_storage_sweep

    response = await world.client.delete("/auth/me", headers=headers)
    assert response.status_code == 204
    await _handle_storage_sweep(world.settings, {"user_id": str(user_id)})


async def _all_redis_text(redis: Any) -> str:
    """Every key name and every string, hash and stream value, as one blob."""
    parts: list[str] = []
    async for key in redis.scan_iter(match="*"):
        parts.append(key)
        kind = await redis.type(key)
        if kind == "string":
            parts.append(str(await redis.get(key)))
        elif kind == "hash":
            parts.append(json.dumps(await redis.hgetall(key)))
        elif kind == "stream":
            parts.append(json.dumps(await redis.xrange(key)))
    return "\n".join(parts)


@pytest.mark.asyncio
async def test_quota_carryover_same_google_sub_keeps_todays_counts(world: World) -> None:
    redis, a = world.redis, world.a
    sub = await _google_sub(a.id)
    await _use_quota(redis, a.id)

    await _delete_and_sweep(world, a.id, a.headers)
    new_id = await _sign_in_google(world, sub=sub, email=f"again-{uuid4()}@example.com")
    try:
        assert new_id != a.id
        assert await _daily_counts(redis, new_id) == _USED
        assert await quota.live_talk_used_seconds(redis, new_id) == 300
        # The carried counts are enforced: one image generation was today's cap.
        new_user = User(id=new_id, plan="pro")
        assert not await counters.reserve("image_generation", redis, new_user, _pro_caps(1))
        # The raise-only DB heal (the new account has no usage rows) keeps them.
        await quota.heal_usage_drift(redis, str(new_id), 10)
        assert await quota.get_daily_usage(redis, str(new_id)) == 1234
        # Used once: nothing is left to carry into a third account.
        assert [key async for key in redis.scan_iter(match="quota_carry:*")] == []
    finally:
        await delete_accounts(new_id)


@pytest.mark.asyncio
async def test_quota_carryover_same_apple_sub_keeps_todays_counts(world: World) -> None:
    redis, a = world.redis, world.a
    apple_sub = f"apple-{uuid4()}"
    async with SessionLocal() as session:
        row = await session.get(User, a.id)
        assert row is not None
        row.apple_sub = apple_sub
        await session.commit()
    await _use_quota(redis, a.id)

    await _delete_and_sweep(world, a.id, a.headers)
    payload = {"sub": apple_sub, "email": f"again-{uuid4()}@example.com", "email_verified": "true"}
    with patch(
        "app.modules.account.service.verify_apple_id_token", AsyncMock(return_value=payload)
    ):
        response = await world.client.post("/auth/apple", json={"id_token": "t", "nonce": "n"})
    assert response.status_code == 200, response.text
    new_id = UUID(response.json()["user"]["id"])
    try:
        assert await _daily_counts(redis, new_id) == _USED
        assert await quota.live_talk_used_seconds(redis, new_id) == 300
    finally:
        await delete_accounts(new_id)


@pytest.mark.asyncio
async def test_quota_carryover_different_sub_starts_fresh(world: World) -> None:
    redis, a = world.redis, world.a
    await _use_quota(redis, a.id)

    await _delete_and_sweep(world, a.id, a.headers)
    new_id = await _sign_in_google(
        world, sub=f"other-{uuid4()}", email=f"other-{uuid4()}@example.com"
    )
    try:
        assert await _daily_counts(redis, new_id) == dict.fromkeys(DAILY_PREFIXES, 0)
        assert await quota.live_talk_used_seconds(redis, new_id) == 0
    finally:
        await delete_accounts(new_id)


@pytest.mark.asyncio
async def test_quota_carryover_next_day_starts_fresh(world: World) -> None:
    redis, a = world.redis, world.a
    sub = await _google_sub(a.id)
    await _use_quota(redis, a.id)
    month = quota.utc_month()
    await _delete_and_sweep(world, a.id, a.headers)

    tomorrow = quota.utc_today() + timedelta(days=1)
    with (
        patch("app.services.quota.carryover.utc_today", return_value=tomorrow),
        patch("app.services.quota.carryover.utc_month", return_value=month),
    ):
        new_id = await _sign_in_google(world, sub=sub, email=f"again-{uuid4()}@example.com")
    try:
        assert await _daily_counts(redis, new_id, tomorrow) == dict.fromkeys(DAILY_PREFIXES, 0)
        # Still the same month: live talk minutes are monthly, so they carry.
        assert await quota.live_talk_used_seconds(redis, new_id, month=month) == 300
    finally:
        await delete_accounts(new_id)


@pytest.mark.asyncio
async def test_quota_carryover_next_month_starts_live_talk_fresh(world: World) -> None:
    redis, a = world.redis, world.a
    sub = await _google_sub(a.id)
    await _use_quota(redis, a.id)
    await _delete_and_sweep(world, a.id, a.headers)

    with (
        patch(
            "app.services.quota.carryover.utc_today",
            return_value=quota.utc_today() + timedelta(days=40),
        ),
        patch("app.services.quota.carryover.utc_month", return_value="2999-01"),
    ):
        new_id = await _sign_in_google(world, sub=sub, email=f"again-{uuid4()}@example.com")
    try:
        assert await quota.live_talk_used_seconds(redis, new_id, month="2999-01") == 0
    finally:
        await delete_accounts(new_id)


@pytest.mark.asyncio
async def test_quota_carryover_snapshot_holds_no_raw_sub(world: World) -> None:
    from app.modules.account import quota_carryover

    redis, a = world.redis, world.a
    sub = await _google_sub(a.id)
    await _use_quota(redis, a.id)
    await _delete_and_sweep(world, a.id, a.headers)

    keys = [key async for key in redis.scan_iter(match="quota_carry:*")]
    assert keys == [quota_carryover.carry_key(world.settings, "google", sub)]
    assert sub not in await _all_redis_text(redis)
    assert str(a.id) not in await redis.get(keys[0])
    ttl = await redis.ttl(keys[0])
    month_left = (quota.next_month_start() - datetime.now(UTC)).total_seconds()
    assert month_left - 60 <= ttl <= 35 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_quota_carryover_failure_never_fails_delete(world: World) -> None:
    from redis.exceptions import ConnectionError as RedisConnectionError

    a = world.a
    await _use_quota(world.redis, a.id)
    with patch(
        "app.services.quota.read_carried_usage",
        AsyncMock(side_effect=RedisConnectionError("down")),
    ):
        response = await world.client.delete("/auth/me", headers=a.headers)
    assert response.status_code == 204
    async with SessionLocal() as session:
        assert await session.get(User, a.id) is None


def test_quota_carryover_names_every_daily_counter() -> None:
    """A daily cap added to the quota package must be carried too."""
    import importlib
    import inspect
    import pkgutil
    import re

    sources = "".join(
        inspect.getsource(importlib.import_module(f"app.services.quota.{module.name}"))
        for module in pkgutil.iter_modules(quota.__path__)
    )
    used = set(re.findall(r'daily_key\(\s*"([a-z:]+)"', sources))
    used |= {spec.prefix for spec in counters.COUNTERS.values()}
    assert used - {"usage:heal"} <= set(quota.DAILY_COUNTER_PREFIXES)
    assert set(quota.DAILY_COUNTER_PREFIXES) == set(DAILY_PREFIXES)
