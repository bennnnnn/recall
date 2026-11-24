"""A chat turn takes one of the day's messages, the plan's allowance (Free 10; Pro has no
daily cap), and gives it back when it saves no reply.

The token budget stays behind it as a cost guardrail: a turn's prompt cost about 10k
tokens, so a token allowance gave Free about ten messages (audit, 2026-11-06).
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import QuotaExceededError
from app.modules.chat import turn_resources
from app.services import quota as quota_service
from app.services.quota.messages import QUOTA_EXCEEDED_MESSAGE_PAID
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import FakeSessionCM, turn_deps

_SETTINGS = Settings(max_output_tokens=1_000, daily_message_limit=3)


def _user(plan: str = "free") -> MagicMock:
    return make_user(plan=plan)


def _no_session() -> FakeSessionCM:
    raise AssertionError("reserving a turn opened a database session")


def _resources(fake_redis, user) -> turn_resources.TurnResources:
    return turn_resources.TurnResources(
        deps=turn_deps(session_factory=_no_session),
        redis=fake_redis,
        user_id=user.id,
        chat_id=uuid4(),
        lock_key="lock",
        lock_token="token",
    )


async def _take(fake_redis, user) -> turn_resources.TurnResources:
    res = _resources(fake_redis, user)
    await res.reserve(user=user, content="hi", model="free-chat", settings=_SETTINGS)
    return res


async def test_a_turn_takes_one_of_the_days_messages_and_the_next_past_them_is_refused(
    fake_redis,
) -> None:
    user = _user()
    for _ in range(3):
        await _take(fake_redis, user)
    assert await quota_service.messages_used(fake_redis, user.id) == 3
    with pytest.raises(QuotaExceededError):
        await _take(fake_redis, user)
    # The refused turn took neither a message nor tokens.
    assert await quota_service.messages_used(fake_redis, user.id) == 3


async def test_a_turn_that_saves_no_reply_gives_its_message_back(fake_redis) -> None:
    user = _user()
    res = await _take(fake_redis, user)
    await res.refund()
    assert await quota_service.messages_used(fake_redis, user.id) == 0
    assert await quota_service.get_daily_usage(fake_redis, str(user.id)) == 0


@pytest.mark.parametrize(("plan", "messages", "unlimited"), [("free", 10, False), ("pro", 0, True)])
def test_each_plan_offers_its_messages(plan: str, messages: int, unlimited: bool) -> None:
    """Free counts ten; Pro has no count (0, which the phone shows as none)."""
    assert quota_service.daily_message_limit(_user(plan), Settings()) == messages
    assert quota_service.unlimited_messages(_user(plan), Settings()) is unlimited


async def test_pro_is_never_refused_for_its_message_count(fake_redis) -> None:
    """Pro's chat is unlimited: past the old 1,000 every turn goes through, still counted
    (so a turn that saves no reply gives its message back)."""
    user = _user("pro")
    settings = Settings(max_output_tokens=1_000)
    for _ in range(1_200):
        res = _resources(fake_redis, user)
        await res.reserve(user=user, content="hi", model="free-chat", settings=settings)
    assert await quota_service.messages_used(fake_redis, user.id) == 1_200
    await res.refund()
    assert await quota_service.messages_used(fake_redis, user.id) == 1_199


async def test_pro_still_meets_its_token_guard(fake_redis) -> None:
    """The hidden cost guard stays: a Pro day past its tokens is refused with the paid
    plan's words, which name no message count."""
    user = _user("pro")
    settings = Settings(max_output_tokens=1_000, daily_token_limit_pro=1_500)
    with pytest.raises(QuotaExceededError) as refused:
        for _ in range(5):
            await _resources(fake_redis, user).reserve(
                user=user, content="hi", model="free-chat", settings=settings
            )
    assert refused.value.message == QUOTA_EXCEEDED_MESSAGE_PAID
    assert not any(count in refused.value.message for count in ("1,000", "1000"))
