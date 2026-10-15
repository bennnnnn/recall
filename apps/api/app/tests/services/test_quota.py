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


def _plus_user() -> MagicMock:
    user = MagicMock()
    user.plan = "plus"
    return user


def test_daily_limit_for_user(settings):
    assert quota_service.daily_limit_for_user(_free_user(), settings) == 100_000
    assert quota_service.daily_limit_for_user(_pro_user(), settings) == 500_000


def test_quota_exceeded_message(settings):
    """Free is told it can upgrade; paid plans are not. Plan names stay in the app."""
    assert "Upgrade" in quota_service.quota_exceeded_message(_free_user())
    for user in (_plus_user(), _pro_user()):
        assert "Upgrade" not in quota_service.quota_exceeded_message(user)
    for user in (_free_user(), _plus_user(), _pro_user()):
        assert "Pro" not in quota_service.quota_exceeded_message(user)


@pytest.mark.parametrize(
    "plan, tokens, stt, tts, images",
    [("free", 100_000, 0, 0, 3), ("plus", 500_000, 200, 100, 10), ("pro", 500_000, 200, 100, 15)],
)
def test_per_plan_daily_caps(plan, tokens, stt, tts, images):
    user = MagicMock()
    user.plan = plan
    settings = Settings()
    assert quota_service.daily_limit_for_user(user, settings) == tokens
    assert quota_service.speech_transcription_limit_for_user(user, settings) == stt
    assert quota_service.speech_tts_limit_for_user(user, settings) == tts
    assert quota_service.image_generation_limit_for_user(user, settings) == images


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
    result = await quota_service.reserve_usage(fake_redis, "u1", requested, daily_limit=limit)
    assert result is allowed


@pytest.mark.asyncio
async def test_record_usage_increments(fake_redis):
    total = await quota_service.record_usage(fake_redis, "u1", 500)
    assert total == 500
    total = await quota_service.record_usage(fake_redis, "u1", 200)
    assert total == 700


@pytest.mark.asyncio
async def test_record_usage_caps_overshoot_at_daily_limit(fake_redis):
    """A turn whose actual > reserved delta must not push the daily counter
    past the limit — otherwise subsequent reserve_usage checks under-report
    remaining quota and the user keeps getting turns past the cap."""
    await fake_redis.set(quota_service._usage_key("u1", quota_service.utc_today()), 99_500)
    total = await quota_service.record_usage(fake_redis, "u1", 2000, daily_limit=100_000)
    assert total == 100_000  # clipped, not 101_500
    assert await quota_service.get_daily_usage(fake_redis, "u1") == 100_000


@pytest.mark.asyncio
async def test_adjust_usage_caps_overshoot(fake_redis):
    await fake_redis.set(quota_service._usage_key("u1", quota_service.utc_today()), 99_000)
    # reserved 1000, actual 5000 → delta +4000 would push to 103_000; clip.
    total = await quota_service.adjust_usage(
        fake_redis, "u1", reserved=1000, actual=5000, daily_limit=100_000
    )
    assert total == 100_000


@pytest.mark.asyncio
async def test_record_usage_without_limit_does_not_cap(fake_redis):
    """Backward compat: callers that don't pass daily_limit get the raw total
    (no clipping) — existing callers (e.g. admin tooling) aren't affected."""
    await fake_redis.set(quota_service._usage_key("u1", quota_service.utc_today()), 99_500)
    total = await quota_service.record_usage(fake_redis, "u1", 2000)
    assert total == 101_500


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

    from app.modules.chat.post_turn import seed_usage_from_db

    session = AsyncMock()
    user_id = uuid4()
    # Redis already at 500 — skip Neon entirely (heal-on-every-turn was a
    # round-trip on the send path).
    await fake_redis.set(f"usage:{user_id}:{quota_service.utc_today().isoformat()}", 500)
    with (
        patch(
            "app.repositories.usage.get_total_for_date", AsyncMock(return_value=500)
        ) as get_total,
    ):
        await seed_usage_from_db(fake_redis, session, user_id)
        get_total.assert_not_awaited()
    # Redis unchanged (no drift)
    assert (
        int(await fake_redis.get(f"usage:{user_id}:{quota_service.utc_today().isoformat()}")) == 500
    )


@pytest.mark.asyncio
async def test_seed_usage_from_db_does_not_heal_warm_redis(fake_redis):
    """Warm Redis skips Neon even if the counter is below the DB total."""
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from app.modules.chat.post_turn import seed_usage_from_db

    session = AsyncMock()
    user_id = uuid4()
    key = f"usage:{user_id}:{quota_service.utc_today().isoformat()}"
    await fake_redis.set(key, 200)
    with patch(
        "app.repositories.usage.get_total_for_date", AsyncMock(return_value=500)
    ) as get_total:
        await seed_usage_from_db(fake_redis, session, user_id)
    get_total.assert_not_awaited()
    assert int(await fake_redis.get(key)) == 200


@pytest.mark.asyncio
async def test_heal_usage_drift_raises_stale_redis_to_db_total(fake_redis):
    await fake_redis.set(f"usage:u1:{quota_service.utc_today().isoformat()}", 200)
    await quota_service.heal_usage_drift(fake_redis, "u1", 500)
    assert int(await fake_redis.get(f"usage:u1:{quota_service.utc_today().isoformat()}")) == 500


@pytest.mark.asyncio
async def test_heal_usage_drift_does_not_lower_live_redis(fake_redis):
    await fake_redis.set(f"usage:u1:{quota_service.utc_today().isoformat()}", 800)
    await quota_service.heal_usage_drift(fake_redis, "u1", 500)
    assert int(await fake_redis.get(f"usage:u1:{quota_service.utc_today().isoformat()}")) == 800


@pytest.mark.asyncio
async def test_seed_usage_from_db_heals_when_flag_set(fake_redis):
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from app.modules.chat.post_turn import seed_usage_from_db

    session = AsyncMock()
    user_id = uuid4()
    key = f"usage:{user_id}:{quota_service.utc_today().isoformat()}"
    await fake_redis.set(key, 200)
    await quota_service.mark_usage_needs_heal(fake_redis, str(user_id))
    with patch(
        "app.repositories.usage.get_total_for_date", AsyncMock(return_value=500)
    ) as get_total:
        await seed_usage_from_db(fake_redis, session, user_id)
    get_total.assert_awaited_once()
    assert int(await fake_redis.get(key)) == 500
    assert await quota_service.usage_needs_heal(fake_redis, str(user_id)) is False


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
    limit = quota_service.speech_transcription_limit_for_user(_plus_user(), settings)
    assert await quota_service.reserve_speech_transcription(fake_redis, user_id, limit=limit)
    await quota_service.refund_speech_transcription(fake_redis, user_id)
    assert await quota_service.reserve_speech_transcription(fake_redis, user_id, limit=limit)


@pytest.mark.asyncio
async def test_reserve_speech_tts_enforces_limit(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = quota_service.speech_tts_limit_for_user(_plus_user(), settings)
    assert limit > 0
    for _ in range(limit):
        assert await quota_service.reserve_speech_tts(fake_redis, user_id, limit=limit) is True
    assert await quota_service.reserve_speech_tts(fake_redis, user_id, limit=limit) is False


@pytest.mark.asyncio
async def test_refund_speech_tts(fake_redis, settings):
    from uuid import uuid4

    user_id = uuid4()
    limit = quota_service.speech_tts_limit_for_user(_plus_user(), settings)
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


# ── Live talk minutes ────────────────────────────────────────────────────────


def test_live_talk_allowance_is_monthly_minutes_per_plan():
    settings = Settings()
    assert quota_service.live_talk_allowance_seconds(_free_user(), settings) == 0
    assert quota_service.live_talk_allowance_seconds(_plus_user(), settings) == 0
    assert quota_service.live_talk_allowance_seconds(_pro_user(), settings) == 60 * 60


async def _reserve(redis, user_id, *, allowance=1000, max_session=600, min_session=60) -> int:
    return await quota_service.reserve_live_talk_seconds(
        redis,
        user_id,
        allowance_seconds=allowance,
        max_session_seconds=max_session,
        min_session_seconds=min_session,
    )


@pytest.mark.asyncio
async def test_live_talk_reserve_caps_a_session_and_stops_at_the_allowance(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    assert await _reserve(fake_redis, user_id) == 600
    assert await _reserve(fake_redis, user_id) == 400
    assert await _reserve(fake_redis, user_id) == 0
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == 1000


@pytest.mark.asyncio
async def test_live_talk_reserve_refuses_less_than_the_minimum_session(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    assert await _reserve(fake_redis, user_id, allowance=650) == 600
    assert await _reserve(fake_redis, user_id, allowance=650) == 0
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == 600


@pytest.mark.asyncio
async def test_live_talk_reserve_without_minutes_takes_nothing(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    assert await _reserve(fake_redis, user_id, allowance=0) == 0
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == 0


@pytest.mark.asyncio
async def test_parallel_live_talk_reserves_never_pass_the_allowance(fake_redis):
    """Two mints read the same balance; the one that lands past it gives back."""
    from uuid import uuid4

    user_id = uuid4()
    assert await _reserve(fake_redis, user_id) == 600

    class _StaleRead:
        """Answers GET with the balance before the first mint landed."""

        def __getattr__(self, name):
            return getattr(fake_redis, name)

        async def get(self, _key):
            return "0"

    assert await _reserve(_StaleRead(), user_id) == 400
    assert await _reserve(_StaleRead(), user_id) == 0
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == 1000


async def _reserve_started(redis, user_id, session_id, *, reserved, seconds_ago, month=None):
    from datetime import UTC, datetime

    started_ms = int(datetime.now(UTC).timestamp() * 1000) - seconds_ago * 1000
    month = month or quota_service.utc_month()
    await redis.incrby(f"livetalk_sec:{user_id}:{month}", reserved)
    await redis.set(f"livetalk_res:{user_id}:{session_id}", f"{reserved}:{started_ms}:{month}")


@pytest.mark.asyncio
async def test_live_talk_settle_charges_the_time_that_passed(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    await _reserve_started(fake_redis, user_id, "call-1", reserved=600, seconds_ago=90)
    charged = await quota_service.settle_live_talk_session(fake_redis, user_id, "call-1")
    assert charged is not None and 90 <= charged <= 92
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == charged


@pytest.mark.asyncio
async def test_live_talk_settle_never_refunds_past_the_reservation(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    await _reserve_started(fake_redis, user_id, "call-1", reserved=600, seconds_ago=5_000)
    assert await quota_service.settle_live_talk_session(fake_redis, user_id, "call-1") == 600
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == 600


@pytest.mark.asyncio
async def test_live_talk_settles_once_and_unreported_sessions_stay_charged(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    await _reserve_started(fake_redis, user_id, "call-1", reserved=600, seconds_ago=30)
    await _reserve_started(fake_redis, user_id, "call-2", reserved=300, seconds_ago=10)
    first = await quota_service.settle_live_talk_session(fake_redis, user_id, "call-1")
    assert first is not None
    assert await quota_service.settle_live_talk_session(fake_redis, user_id, "call-1") is None
    assert await quota_service.settle_live_talk_session(fake_redis, user_id, "unknown") is None
    # call-2 never reported its end: the full 300 seconds stay charged.
    assert await quota_service.live_talk_used_seconds(fake_redis, user_id) == first + 300


@pytest.mark.asyncio
async def test_live_talk_settle_refunds_the_month_it_was_reserved_in(fake_redis):
    from uuid import uuid4

    user_id = uuid4()
    await _reserve_started(
        fake_redis, user_id, "call-1", reserved=600, seconds_ago=60, month="2026-09"
    )
    await quota_service.settle_live_talk_session(fake_redis, user_id, "call-1")
    september = await quota_service.live_talk_used_seconds(fake_redis, user_id, month="2026-09")
    assert 60 <= september <= 62


def test_live_talk_minutes_renew_on_the_first_of_the_month():
    from datetime import UTC, datetime

    december = datetime(2026, 12, 31, 23, 59, tzinfo=UTC)
    assert quota_service.next_month_start(december) == datetime(2027, 1, 1, tzinfo=UTC)
    assert quota_service.utc_month(december) == "2026-12"


@pytest.mark.asyncio
async def test_global_spend_unlimited_when_limit_zero(fake_redis):
    settings = Settings(daily_global_spend_usd=0)
    await quota_service.record_global_spend(fake_redis, 50.0)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is False


@pytest.mark.asyncio
async def test_global_spend_exceeded_after_recording(fake_redis):
    settings = Settings(daily_global_spend_usd=1.0)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is False
    await quota_service.record_global_spend(fake_redis, 0.4)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is False
    await quota_service.record_global_spend(fake_redis, 0.6)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is True


@pytest.mark.asyncio
async def test_global_spend_redis_error_fails_closed():
    settings = Settings(daily_global_spend_usd=10.0)

    class _Boom:
        async def get(self, _key: str) -> None:
            from redis.exceptions import RedisError

            raise RedisError("down")

    assert await quota_service.global_spend_exceeded(_Boom(), settings) is True  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_voice_spend_counts_toward_global_cap(fake_redis):
    settings = Settings(daily_global_spend_usd=0.05)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is False
    await quota_service.record_voice_spend(fake_redis, 0.08)
    assert await quota_service.global_spend_exceeded(fake_redis, settings) is True
