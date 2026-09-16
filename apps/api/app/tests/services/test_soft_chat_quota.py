from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import QuotaExceededError
from app.services.chat import turn_resources as resources
from app.services.chat.turn_prep import StreamContext


def _user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.plan = "free"
    return user


@pytest.mark.asyncio
async def test_soft_quota_allows_turn_below_limit_without_reservation() -> None:
    user = _user()
    quota = SimpleNamespace(
        get_daily_usage=AsyncMock(return_value=99),
        daily_limit_for_user=lambda *_args: 100,
        reserve_usage=AsyncMock(),
    )
    seams = SimpleNamespace(quota_service=quota)

    reserved = await resources.reserve_turn_quota(
        seams,
        AsyncMock(),
        user=user,
        content="hi",
        model="free-chat",
        settings=Settings(),
        daily_limit=100,
        seed=False,
    )

    assert reserved == 0
    quota.get_daily_usage.assert_awaited_once()
    quota.reserve_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_soft_quota_blocks_only_when_user_is_already_at_limit() -> None:
    user = _user()
    quota = SimpleNamespace(
        get_daily_usage=AsyncMock(return_value=100),
        daily_limit_for_user=lambda *_args: 100,
    )
    seams = SimpleNamespace(quota_service=quota)

    with pytest.raises(QuotaExceededError):
        await resources.reserve_turn_quota(
            seams,
            AsyncMock(),
            user=user,
            content="hi",
            model="free-chat",
            settings=Settings(),
            daily_limit=100,
            seed=False,
        )


@pytest.mark.asyncio
async def test_soft_quota_skips_prompt_top_up_when_nothing_was_reserved() -> None:
    user = _user()
    quota = SimpleNamespace(reserve_usage=AsyncMock())
    seams = SimpleNamespace(
        quota_service=quota,
        prompt_weighted_reserve_tokens=MagicMock(return_value=500),
    )
    redis = AsyncMock()
    res = resources.TurnResources(
        redis=redis,
        user_id=user.id,
        chat_id=uuid4(),
        lock_key="chatprep:test",
        lock_token="token",
        reserved_tokens=0,
    )
    ctx = StreamContext(
        user_id=user.id,
        chat_id=res.chat_id,
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hello"}],
        run_title=False,
        user_message_content="hello",
        reserved_tokens=0,
        max_output_tokens=100,
        user=user,
    )

    await resources.top_up_reserve_for_prompt(
        seams,
        res,
        settings=Settings(),
        ctx=ctx,
        daily_limit=100,
    )

    assert res.reserved_tokens == 0
    assert ctx.reserved_tokens == 0
    seams.prompt_weighted_reserve_tokens.assert_not_called()
    quota.reserve_usage.assert_not_awaited()
