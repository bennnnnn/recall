"""A chat turn takes one of the day's messages, the plan's allowance (Free 10, Plus 200,
Pro 1,000), and gives it back when it saves no reply.

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


@pytest.mark.parametrize(("plan", "messages"), [("free", 10), ("plus", 200), ("pro", 1000)])
def test_each_plan_offers_its_messages(plan: str, messages: int) -> None:
    assert quota_service.daily_message_limit(_user(plan), Settings()) == messages
