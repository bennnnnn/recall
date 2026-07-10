from datetime import date
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services import quota as quota_service


@pytest.fixture
def settings() -> Settings:
    return Settings(daily_token_limit=100_000, daily_token_limit_pro=500_000)


def _pro_user() -> MagicMock:
    user = MagicMock()
    user.plan = "pro"
    return user


def _free_user() -> MagicMock:
    user = MagicMock()
    user.plan = "free"
    return user


def test_daily_limit_for_user(settings):
    assert quota_service.daily_limit_for_user(_free_user(), settings) == 100_000
    assert quota_service.daily_limit_for_user(_pro_user(), settings) == 500_000


def test_quota_exceeded_message(settings):
    assert "Pro" in quota_service.quota_exceeded_message(_free_user())
    assert "Pro" not in quota_service.quota_exceeded_message(_pro_user())


@pytest.mark.parametrize(
    "used, requested, allowed",
    [
        (0, 1000, True),
        (99_000, 2000, False),
        (100_000, 1, False),
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
    await fake_redis.set(f"usage:u1:{day}", 99_500)
    limit = quota_service.daily_limit_for_user(_free_user(), settings)

    allowed = await quota_service.reserve_usage(fake_redis, "u1", 1000, daily_limit=limit)
    assert allowed is False
    assert int(await fake_redis.get(f"usage:u1:{day}")) == 99_500


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
async def test_refund_usage_floor_preserves_ttl(fake_redis):
    await quota_service.record_usage(fake_redis, "u1", 50)
    key = quota_service._usage_key("u1", quota_service.utc_today())
    ttl_before = await fake_redis.ttl(key)
    assert ttl_before > 0
    await quota_service.refund_usage(fake_redis, "u1", 100)  # floors at 0
    assert await quota_service.get_daily_usage(fake_redis, "u1") == 0
    assert await fake_redis.ttl(key) == ttl_before


@pytest.mark.asyncio
async def test_has_daily_usage_key(fake_redis):
    assert await quota_service.has_daily_usage_key(fake_redis, "u1") is False
    await fake_redis.set("usage:u1:2026-01-01", 100)
    assert await quota_service.has_daily_usage_key(fake_redis, "u1", day=date(2026, 1, 1)) is True


@pytest.mark.asyncio
async def test_seed_usage_from_db_skips_db_when_redis_key_warm(fake_redis):
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from app.services.chat.post_turn import seed_usage_from_db

    session = AsyncMock()
    user_id = uuid4()
    await fake_redis.set(f"usage:{user_id}:{quota_service.utc_today().isoformat()}", 500)
    with patch("app.services.chat.usage_repo.get_total_for_date", AsyncMock()) as get_total:
        await seed_usage_from_db(fake_redis, session, user_id)
        get_total.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_refund_image_upload_floors_at_zero(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = 5
    assert await quota_service.reserve_image_upload(fake_redis, user_id, limit=limit) is True
    assert await quota_service.get_image_upload_count(fake_redis, user_id) == 1
    await quota_service.refund_image_upload(fake_redis, user_id)
    assert await quota_service.get_image_upload_count(fake_redis, user_id) == 0
    await quota_service.refund_image_upload(fake_redis, user_id)
    assert await quota_service.get_image_upload_count(fake_redis, user_id) == 0


def test_image_upload_limit_for_user(settings):
    assert quota_service.image_upload_limit_for_user(_free_user(), settings) == 5
    assert quota_service.image_upload_limit_for_user(_pro_user(), settings) == 30


@pytest.mark.asyncio
async def test_reserve_speech_transcription_enforces_limit(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = quota_service.speech_transcription_limit_for_user(_free_user(), settings)
    for _ in range(limit):
        assert (
            await quota_service.reserve_speech_transcription(fake_redis, user_id, limit=limit)
            is True
        )
    assert (
        await quota_service.reserve_speech_transcription(fake_redis, user_id, limit=limit) is False
    )


@pytest.mark.asyncio
async def test_refund_speech_transcription(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = quota_service.speech_transcription_limit_for_user(_free_user(), settings)
    assert await quota_service.reserve_speech_transcription(fake_redis, user_id, limit=limit)
    await quota_service.refund_speech_transcription(fake_redis, user_id)
    assert await quota_service.reserve_speech_transcription(fake_redis, user_id, limit=limit)


@pytest.mark.asyncio
async def test_reserve_speech_tts_enforces_limit(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = quota_service.speech_tts_limit_for_user(_free_user(), settings)
    for _ in range(limit):
        assert await quota_service.reserve_speech_tts(fake_redis, user_id, limit=limit) is True
    assert await quota_service.reserve_speech_tts(fake_redis, user_id, limit=limit) is False


@pytest.mark.asyncio
async def test_refund_speech_tts(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = quota_service.speech_tts_limit_for_user(_free_user(), settings)
    assert await quota_service.reserve_speech_tts(fake_redis, user_id, limit=limit)
    await quota_service.refund_speech_tts(fake_redis, user_id)
    assert await quota_service.reserve_speech_tts(fake_redis, user_id, limit=limit)


@pytest.mark.asyncio
async def test_reserve_tavily_search_enforces_limit(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = 3
    for _ in range(limit):
        assert await quota_service.reserve_tavily_search(fake_redis, user_id, limit=limit) is True
    assert await quota_service.reserve_tavily_search(fake_redis, user_id, limit=limit) is False


def test_image_generation_limit_for_user(settings):
    settings = Settings(daily_image_generations=0, daily_image_generations_pro=10)
    assert quota_service.image_generation_limit_for_user(_free_user(), settings) == 0
    assert quota_service.image_generation_limit_for_user(_pro_user(), settings) == 10


@pytest.mark.asyncio
async def test_reserve_image_generation_blocks_free_plan(fake_redis, settings):
    from uuid import uuid4

    settings = Settings(daily_image_generations=0, daily_image_generations_pro=10)
    user_id = uuid4()
    assert (
        await quota_service.reserve_image_generation(
            fake_redis,
            user_id,
            limit=quota_service.image_generation_limit_for_user(_free_user(), settings),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reserve_image_generation_enforces_pro_limit(fake_redis):
    from uuid import uuid4

    settings = Settings(daily_image_generations_pro=2)
    user_id = uuid4()
    limit = quota_service.image_generation_limit_for_user(_pro_user(), settings)
    for _ in range(limit):
        assert (
            await quota_service.reserve_image_generation(fake_redis, user_id, limit=limit) is True
        )
    assert await quota_service.reserve_image_generation(fake_redis, user_id, limit=limit) is False


@pytest.mark.asyncio
async def test_refund_image_generation(fake_redis):
    from uuid import uuid4

    settings = Settings(daily_image_generations_pro=5)
    user_id = uuid4()
    limit = quota_service.image_generation_limit_for_user(_pro_user(), settings)
    assert await quota_service.reserve_image_generation(fake_redis, user_id, limit=limit)
    await quota_service.refund_image_generation(fake_redis, user_id)
    assert await quota_service.reserve_image_generation(fake_redis, user_id, limit=limit)
