import pytest

from app.core.config import Settings
from app.services import quota as quota_service


@pytest.fixture
def settings() -> Settings:
    return Settings(daily_token_limit=30_000)


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
    result = await quota_service.can_spend(fake_redis, "u1", requested, settings)
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

    allowed = await quota_service.reserve_usage(fake_redis, "u1", 1000, settings)
    assert allowed is False
    assert int(await fake_redis.get(f"usage:u1:{day}")) == 29_500


@pytest.mark.asyncio
async def test_reserve_and_adjust(fake_redis, settings):
    reserved = 1000
    assert await quota_service.reserve_usage(fake_redis, "u1", reserved, settings) is True
    await quota_service.adjust_usage(fake_redis, "u1", reserved, 700)
    assert await quota_service.get_daily_usage(fake_redis, "u1") == 700


@pytest.mark.asyncio
async def test_refund_usage(fake_redis):
    await quota_service.record_usage(fake_redis, "u1", 500)
    await quota_service.refund_usage(fake_redis, "u1", 200)
    assert await quota_service.get_daily_usage(fake_redis, "u1") == 300
