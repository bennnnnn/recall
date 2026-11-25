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


@pytest.fixture
def web_search_registered():
    """The web_search tool as production registers it at startup."""
    from app.gateways.mcp import registry
    from app.modules.web_search import WebSearchAdapter

    registry.register(WebSearchAdapter(Settings(tavily_api_key="k", web_search_enabled=True)))


def _context(user, res, settings):
    """A turn's context as stream_entry makes it: its one search budget made before the
    prep, keeping the reservation's message once a search reaches a provider."""
    from app.modules.chat.turn_prep import StreamContext
    from app.modules.web_search import turn_search_budget

    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "who won the race today?"}],
        run_title=False,
        user_message_content="who won the race today?",
        reserved_tokens=res.reserved_tokens,
        max_output_tokens=1_000,
        user=user,
        user_timezone="UTC",
        search_budget=turn_search_budget(settings, user, keep_message=res.keep_message),
    )
    res.context = ctx
    ctx.message_day = res.message_day
    return ctx


def _search_call(call_id: str, query: str) -> dict:
    import json

    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "web_search", "arguments": json.dumps({"query": query})},
    }


@pytest.mark.parametrize(("plan", "kept"), [("free", True), ("pro", False)])
@pytest.mark.usefixtures("web_search_registered")
async def test_a_turn_whose_search_reached_a_provider_keeps_its_message(
    fake_redis, plan: str, kept: bool
) -> None:
    """Free's search is covered by its message: once one reached a provider, a Stop or a
    dropped socket before any reply no longer gives the message back (it was, and Free
    searched without end). Pro's searches count on their own; its message comes back."""
    from unittest.mock import AsyncMock, patch

    from app.gateways.web_search_gateway import WebSearchHit
    from app.modules.chat.tool_loop import reply_calls

    user = _user(plan)
    settings = Settings(max_output_tokens=1_000, tavily_api_key="k", web_search_enabled=True)
    res = _resources(fake_redis, user)
    await res.reserve(user=user, content="who won today?", model="free-chat", settings=settings)
    ctx = _context(user, res, settings)
    hit = WebSearchHit(title="t", url="https://t.example", snippet="s")
    with patch(
        "app.modules.web_search.search_cache.web_search_gateway.search_web",
        AsyncMock(return_value=[hit]),
    ):
        await reply_calls.answer_into_turn(
            settings,
            fake_redis,
            ctx,
            [_search_call("read", "race winner")],
            "",
            offered=frozenset({"web_search"}),
            on_status=None,
            should_cancel=None,
        )
    await res.refund()  # the user stopped before the first token

    assert await quota_service.messages_used(fake_redis, user.id) == (1 if kept else 0)
    assert (ctx.message_day is None) is kept


@pytest.mark.usefixtures("web_search_registered")
async def test_a_free_turn_makes_one_search_across_the_read_and_the_reply(fake_redis) -> None:
    """The read's search and the reply's own ``web_search`` share the turn's budget: the
    second reaches no provider, and the reply's model is told the message's search is
    used (``_SEARCH_USED``)."""
    from unittest.mock import AsyncMock, patch

    from app.gateways.web_search_gateway import WebSearchHit
    from app.modules.chat.tool_loop import reply_calls
    from app.modules.web_search.tool import _SEARCH_USED

    user = _user("free")
    settings = Settings(max_output_tokens=1_000, tavily_api_key="k", web_search_enabled=True)
    res = _resources(fake_redis, user)
    await res.reserve(user=user, content="who won today?", model="free-chat", settings=settings)
    ctx = _context(user, res, settings)
    search = AsyncMock(return_value=[WebSearchHit(title="t", url="https://t.example", snippet="s")])
    with patch("app.modules.web_search.search_cache.web_search_gateway.search_web", search):
        for call_id, query in (("read", "race winner"), ("reply", "race result today")):
            await reply_calls.answer_into_turn(
                settings,
                fake_redis,
                ctx,
                [_search_call(call_id, query)],
                "",
                offered=frozenset({"web_search"}),
                on_status=None,
                should_cancel=None,
            )

    # Only the read's search reached a provider (its general and dated news queries).
    assert {call.args[1] for call in search.await_args_list} == {"race winner"}
    tool_messages = [m for m in ctx.prompt_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    assert _SEARCH_USED in str(tool_messages[-1]["content"])


@pytest.mark.parametrize(
    ("plan", "content_type", "kept"),
    [
        ("free", "application/pdf", True),
        ("free", "image/png", False),
        ("pro", "application/pdf", False),
    ],
)
async def test_a_turn_sending_a_pdf_keeps_its_message_on_a_plan_whose_ocr_it_covers(
    fake_redis, plan: str, content_type: str, kept: bool
) -> None:
    """A PDF is queued for indexing as soon as the user's row saves, and may be read with
    vision OCR; on Free the message pays for it, so a turn stopped before its first token
    keeps its message (it was given back while the OCR ran, without end). Pro's OCR counts
    on its own; a photo is never OCR'd."""
    from unittest.mock import MagicMock

    user = _user(plan)
    settings = Settings(max_output_tokens=1_000, attachment_ocr_enabled=True)
    res = _resources(fake_redis, user)
    await res.reserve(user=user, content="read this", model="free-chat", settings=settings)
    turn_resources.keep_message_for_scans(
        res, [MagicMock(content_type=content_type)], user, settings
    )
    await res.refund()  # stopped before the first token

    assert await quota_service.messages_used(fake_redis, user.id) == (1 if kept else 0)


@pytest.mark.parametrize(
    ("plan", "settings", "used", "left"),
    [
        ("free", _SETTINGS, 2, True),
        ("free", _SETTINGS, 3, False),
        # Free set to no messages (chat paused): no message left, not "no cap".
        ("free", Settings(daily_message_limit=0), 0, False),
        ("pro", Settings(), 50, True),
    ],
)
async def test_message_left_agrees_with_the_reserve(fake_redis, plan, settings, used, left):
    """The at-cap check before a turn's paid reads answers as ``reserve`` would: a plan set
    to none refuses every turn, so its reads must not start (review of #2590)."""
    user = _user(plan)
    for _ in range(used):
        await quota_service.reserve_message(fake_redis, user, Settings(daily_message_limit=10**6))
    res = _resources(fake_redis, user)
    assert await res.message_left(user, settings) is left
    if not left:
        with pytest.raises(QuotaExceededError):
            await res.reserve(user=user, content="hi", model="free-chat", settings=settings)
