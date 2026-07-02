from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services import quota as quota_service


@pytest.fixture
def settings() -> Settings:
    return Settings(daily_token_limit=30_000, daily_token_limit_pro=500_000)


def _pro_user() -> MagicMock:
    user = MagicMock()
    user.plan = "pro"
    return user


def _free_user() -> MagicMock:
    user = MagicMock()
    user.plan = "free"
    return user


def test_daily_limit_for_user(settings):
    assert quota_service.daily_limit_for_user(_free_user(), settings) == 30_000
    assert quota_service.daily_limit_for_user(_pro_user(), settings) == 500_000


def test_quota_exceeded_message(settings):
    assert "Pro" in quota_service.quota_exceeded_message(_free_user())
    assert "Pro" not in quota_service.quota_exceeded_message(_pro_user())


@pytest.mark.parametrize(
    "used, requested, allowed",
    [
        (0, 1000, True),
        (29_000, 2000, False),
        (30_000, 1, False),
    ],
)
@pytest.mark.asyncio
async def test_quota_enforced(fake_redis, settings, used, requested, allowed):
    from datetime import UTC, datetime

    day = datetime.now(UTC).date().isoformat()
    if used:
        await fake_redis.set(f"usage:u1:{day}", used)
    limit = quota_service.daily_limit_for_user(_free_user(), settings)
    result = await quota_service.can_spend(fake_redis, "u1", requested, daily_limit=limit)
    assert result is allowed


@pytest.mark.asyncio
async def test_record_usage_increments(fake_redis):
    total = await quota_service.record_usage(fake_redis, "u1", 500)
    assert total == 500
    total = await quota_service.record_usage(fake_redis, "u1", 200)
    assert total == 700


@pytest.mark.asyncio
async def test_reserve_usage_rejects_over_limit(fake_redis, settings):
    from datetime import UTC, datetime

    day = datetime.now(UTC).date().isoformat()
    await fake_redis.set(f"usage:u1:{day}", 29_500)
    limit = quota_service.daily_limit_for_user(_free_user(), settings)

    allowed = await quota_service.reserve_usage(fake_redis, "u1", 1000, daily_limit=limit)
    assert allowed is False
    assert int(await fake_redis.get(f"usage:u1:{day}")) == 29_500


@pytest.mark.asyncio
async def test_reserve_and_adjust(fake_redis, settings):
    limit = quota_service.daily_limit_for_user(_free_user(), settings)
    reserved = 1000
    assert await quota_service.reserve_usage(fake_redis, "u1", reserved, daily_limit=limit) is True
    await quota_service.adjust_usage(fake_redis, "u1", reserved, 700)
    assert await quota_service.get_daily_usage(fake_redis, "u1") == 700


@pytest.mark.asyncio
async def test_refund_usage(fake_redis):
    await quota_service.record_usage(fake_redis, "u1", 500)
    await quota_service.refund_usage(fake_redis, "u1", 200)
    assert await quota_service.get_daily_usage(fake_redis, "u1") == 300


@pytest.mark.asyncio
async def test_seed_usage_if_missing_seeds_from_db_when_key_absent(fake_redis):
    """After a Redis flush the counter is gone; seeding restores the DB total."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date().isoformat()
    await quota_service.seed_usage_if_missing(fake_redis, "u1", 12_000)
    assert int(await fake_redis.get(f"usage:u1:{day}")) == 12_000


@pytest.mark.asyncio
async def test_seed_usage_if_missing_does_not_overwrite_live_counter(fake_redis):
    """SET NX must never overwrite a live (non-zero) counter — no double-count."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date().isoformat()
    await fake_redis.set(f"usage:u1:{day}", 3_000)
    await quota_service.seed_usage_if_missing(fake_redis, "u1", 12_000)
    # Live counter wins; the DB total is NOT applied.
    assert int(await fake_redis.get(f"usage:u1:{day}")) == 3_000


@pytest.mark.asyncio
async def test_seed_usage_if_missing_noop_when_db_total_zero(fake_redis):
    from datetime import UTC, datetime

    day = datetime.now(UTC).date().isoformat()
    await quota_service.seed_usage_if_missing(fake_redis, "u1", 0)
    assert await fake_redis.get(f"usage:u1:{day}") is None


@pytest.mark.asyncio
async def test_reserve_image_upload_enforces_limit(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = 5
    for _ in range(limit):
        assert await quota_service.reserve_image_upload(fake_redis, user_id, limit=limit) is True
    assert await quota_service.reserve_image_upload(fake_redis, user_id, limit=limit) is False
    assert await quota_service.get_image_upload_count(fake_redis, user_id) == limit


def test_image_upload_limit_for_user(settings):
    assert quota_service.image_upload_limit_for_user(_free_user(), settings) == 5
    assert quota_service.image_upload_limit_for_user(_pro_user(), settings) == 30
