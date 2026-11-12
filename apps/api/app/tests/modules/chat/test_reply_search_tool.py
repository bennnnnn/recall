"""The reply's own model call carries web_search; a call runs and a second call answers.

Word rules used to decide search: "who won the champions league" was answered from
training data, and "What is going on" opening a chat was searched. The model decides now.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.gateways.decider_gateway import DeciderAnswer, DeciderReply
from app.gateways.mcp import registry
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.chat.prompt_constants.grounding import DENIAL_RETRY_NOTE
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.stream_paths import run_llm_token_stream, run_tool_loop_path
from app.modules.chat.tool_loop import live_denial
from app.modules.chat.tool_loop.reply_calls import ReplyTurn, answered_read, reply_tools
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.web_search import WebSearchAdapter
from app.tests.fakes import isolated_settings, redis_mock
from app.tests.modules.chat.chat_test_support import turn_deps

_SETTINGS = isolated_settings(web_search_enabled=True, mcp_tool_loop_enabled=True)
_HIT = WebSearchHit(title="UCL final", url="https://uefa.example/final", snippet="PSG won.")
_SEARCH_CALL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "web_search", "arguments": '{"query": "champions league winner"}'},
}


@pytest.fixture
def web_search_tool() -> dict[str, Any]:
    """The tool as production registers it at startup."""
    adapter = WebSearchAdapter(_SETTINGS)
    registry.register(adapter)
    return adapter.to_openai_tool()


def _turn(content: str, **fields: Any) -> ReplyTurn:
    values: dict[str, Any] = {
        "content": content,
        "lightweight": False,
        "has_instant_reply": False,
        "has_verified_math": False,
        "has_search_sources": False,
        **fields,
    }
    return ReplyTurn(**values)


def _context(content: str) -> StreamContext:
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": content}],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )


def _model(*calls: tuple[list[str], list[dict[str, Any]]]) -> tuple[Any, list[dict[str, Any]]]:
    """A model whose nth call writes ``calls[n]``'s tokens, then makes its tool calls."""
    seen: list[dict[str, Any]] = []
    plays = iter(calls)

    async def stream_chat_completion(**kwargs: Any) -> AsyncIterator[str]:
        seen.append({**kwargs, "messages": list(kwargs["messages"])})
        tokens, tool_calls = next(plays)
        for token in tokens:
            yield token
        kwargs["tool_calls"].extend(tool_calls)
        kwargs["stream_meta"]["model_alias"] = kwargs["model_alias"]
        if tool_calls:
            kwargs["stream_meta"]["finish_reason"] = "tool_calls"

    return SimpleNamespace(stream_chat_completion=stream_chat_completion), seen


async def _reply(
    ctx: StreamContext, llm: Any, *, accum: StreamAccum | None = None, **kwargs: Any
) -> str:
    tokens = [
        token
        async for token in run_llm_token_stream(
            turn_deps(llm=llm),
            redis_mock(),
            _SETTINGS,
            ctx,
            usage={},
            outcome=None,
            on_reasoning=None,
            accum=accum or StreamAccum(),
            should_cancel=kwargs.pop("should_cancel", None),
            **kwargs,
        )
    ]
    return "".join(tokens)


@pytest.mark.parametrize(
    "content",
    [
        "who won the champions league",
        "what's the population of Ethiopia",
        "is the new iphone worth it",
        # No word rule withholds the tool: the model answers these without calling it.
        "",
        "thanks!",
        "What is going on",
        "remind me to call mom at 5pm",
        "what time is it in Tokyo",
        "why does this return undefined? function add(a, b) { a + b }",
    ],
)
def test_reply_tools_offer_web_search_on_every_reply_the_model_writes(
    web_search_tool: dict[str, Any], content: str
) -> None:
    assert reply_tools(_SETTINGS, _turn(content)) == [web_search_tool]


@pytest.mark.parametrize(
    "answered",
    [
        {"lightweight": True},
        {"has_instant_reply": True},
        {"has_search_sources": True},
        {"has_verified_math": True},
    ],
)
def test_reply_tools_offer_nothing_on_a_turn_already_answered(
    web_search_tool: dict[str, Any], answered: dict[str, bool]
) -> None:
    assert reply_tools(_SETTINGS, _turn("who won the champions league", **answered)) == []


@pytest.mark.parametrize(
    "off",
    [
        {"reply_search_tool_enabled": False},
        {"web_search_enabled": False},
        {"mcp_tool_loop_enabled": False},
    ],
)
def test_reply_tools_follow_the_switches(
    web_search_tool: dict[str, Any], off: dict[str, bool]
) -> None:
    settings = isolated_settings(
        **{"web_search_enabled": True, "mcp_tool_loop_enabled": True, **off}
    )
    assert reply_tools(settings, _turn("who won the champions league")) == []


def test_reply_tools_need_the_registered_tool() -> None:
    registry.clear()
    assert reply_tools(_SETTINGS, _turn("who won the champions league")) == []


@pytest.mark.asyncio
async def test_tool_loop_path_leaves_the_search_to_the_reply(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=None, should_cancel=None
    )
    assert ctx.reply_tools == [web_search_tool]


@pytest.mark.asyncio
async def test_tool_loop_path_offers_nothing_past_the_spend_cap(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=True)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=None, should_cancel=None
    )
    assert ctx.reply_tools == []


@pytest.mark.asyncio
async def test_reply_searches_then_answers_from_the_results(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    ctx.reply_tools = [web_search_tool]
    llm, seen = _model(([], [_SEARCH_CALL]), (["PSG won it."], []))
    statuses: list[tuple[str, str | None]] = []

    async def on_status(phase: str, detail: str | None = None) -> None:
        statuses.append((phase, detail))

    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        text = await _reply(ctx, llm, on_status=on_status)

    assert text == "PSG won it."
    assert seen[0]["tools"] == [web_search_tool]
    # One search a turn: the call that answers carries no tools.
    assert seen[1]["tools"] is None
    call_turn, result = seen[1]["messages"][-2:]
    assert call_turn == {"role": "assistant", "content": None, "tool_calls": [_SEARCH_CALL]}
    assert result["role"] == "tool"
    assert result["tool_call_id"] == "call_1"
    assert _HIT.url in result["content"]
    # The pages the search found become the reply's source chips.
    assert [hit.url for hit in ctx.search_sources] == [_HIT.url]
    assert ("searching", "champions league winner") in statuses
    assert statuses[-1] == ("composing", None)


@pytest.mark.asyncio
async def test_reply_text_before_its_search_gives_way_to_the_answer(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    ctx.reply_tools = [web_search_tool]
    llm, seen = _model((["Let me check."], [_SEARCH_CALL]), (["PSG won it."], []))
    accum = StreamAccum()

    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        await _reply(ctx, llm, accum=accum)

    assert accum.reply_text() == "PSG won it."
    assert accum.retracted == "Let me check."
    assert seen[1]["messages"][-2]["content"] == "Let me check."


@pytest.mark.asyncio
async def test_reply_stopped_during_its_search_ends_there(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    ctx.reply_tools = [web_search_tool]
    llm, seen = _model(([], [_SEARCH_CALL]), (["never written"], []))
    stopped = {"now": False}

    async def search(*_args: Any, **_kwargs: Any) -> tuple[list[WebSearchHit], list[str]]:
        stopped["now"] = True
        return [_HIT], ["q"]

    accum = StreamAccum()
    with patch("app.modules.web_search.tool.run_cached_search", search):
        text = await _reply(ctx, llm, accum=accum, should_cancel=lambda: stopped["now"])

    assert text == ""
    assert len(seen) == 1
    assert accum.was_cancelled


@pytest.mark.asyncio
async def test_reply_call_to_a_tool_it_was_not_offered_is_refused(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    ctx.reply_tools = [web_search_tool]
    image_call = {
        "id": "call_2",
        "type": "function",
        "function": {"name": "generate_image", "arguments": '{"prompt": "a trophy"}'},
    }
    llm, seen = _model(([], [image_call]), (["Here is what I know."], []))

    text = await _reply(ctx, llm)

    assert text == "Here is what I know."
    refusal = seen[1]["messages"][-1]
    assert refusal["role"] == "tool"
    assert refusal["tool_call_id"] == "call_2"
    assert "not available" in refusal["content"]
    assert ctx.search_sources == []


@pytest.mark.asyncio
async def test_reply_without_tools_is_one_call() -> None:
    ctx = _context("explain Newton's third law")
    llm, seen = _model((["Equal and opposite."], []))

    assert await _reply(ctx, llm) == "Equal and opposite."
    assert len(seen) == 1
    assert seen[0]["tools"] is None


@pytest.mark.asyncio
async def test_reply_searches_once_whatever_the_second_call_returns(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    ctx.reply_tools = [web_search_tool]
    llm, seen = _model(
        ([], [_SEARCH_CALL]), (["PSG won it."], [_SEARCH_CALL]), (["never asked"], [])
    )

    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        text = await _reply(ctx, llm)

    assert text == "PSG won it."
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_reply_answers_without_a_search_that_breaks(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("who won the champions league")
    ctx.reply_tools = [web_search_tool]
    prompt = list(ctx.prompt_messages)
    llm, seen = _model(([], [_SEARCH_CALL]), (["From what I know, PSG."], []))

    with patch(
        "app.modules.web_search.tool.run_cached_search",
        AsyncMock(side_effect=RuntimeError("search client bug")),
    ):
        text = await _reply(ctx, llm)

    assert text == "From what I know, PSG."
    # The unanswered call never reaches the provider, which would reject the list.
    assert seen[1]["messages"] == prompt
    assert ctx.search_sources == []


_BEARS = "Perfect. totally unrelated but did the bears win today"
_DENIAL = "I can't check live scores, so I don't know how the Bears did today."
_ANSWER = "The Bears beat the Falcons 27-20."
_DENIALS = {_DENIAL, "Sorry, I can't check live scores!"}
_LESSON_STEP = (
    "## Lesson 1: What a fraction is\n\nA fraction is a part of a whole.\n\n"
    "Which is bigger, 1/2 or 1/3?"
)
_EMAIL_DRAFT = "```email\nSubject: Rent\n\nHi Mr. Lee,\n\nRent will be late this month.\n```"


def _check(denies: float | Exception) -> AsyncMock:
    """The Decider as the denial check: one answer, or a failure."""
    if isinstance(denies, Exception):
        return AsyncMock(side_effect=denies)
    answer = DeciderAnswer(type="noul", noul=denies)
    return AsyncMock(return_value=DeciderReply(answers={"denies": answer}))


@pytest.fixture
def denial_check() -> Iterator[AsyncMock]:
    """The Decider reads the replies in ``_DENIALS`` as denials, and nothing else."""

    async def decide(_settings: Any, **kwargs: Any) -> DeciderReply:
        reply = kwargs["state"].split("The assistant's reply: ", 1)[1]
        answer = DeciderAnswer(type="noul", noul=0.9 if reply in _DENIALS else 0.05)
        return DeciderReply(answers={"denies": answer})

    check = AsyncMock(side_effect=decide)
    with patch("app.gateways.decider_gateway.decide", check):
        yield check


@pytest.mark.parametrize(("denies", "retried"), [(0.65, True), (0.4, True), (0.11, False)])
@pytest.mark.asyncio
async def test_a_reply_is_a_denial_when_the_check_says_so(denies: float, retried: bool) -> None:
    """Pro phone test (2026-11-11): "I can't check live rankings from here" mid-sentence in a
    five-item list went out as it was; a pattern of English openings read it. The Decider
    reads it now: every denial of 40 labelled replies, in five languages, at 0.65 or more,
    every other reply at 0.11 or less."""
    reply = "Here are five of them. I can't check live rankings from here, so this is reputation."
    with patch("app.gateways.decider_gateway.decide", _check(denies)):
        assert await live_denial.denies_live_data(_SETTINGS, "Top 5 in Ethiopia", reply) is retried


@pytest.mark.asyncio
async def test_a_check_that_fails_leaves_the_reply() -> None:
    with patch("app.gateways.decider_gateway.decide", _check(TimeoutError())):
        assert not await live_denial.denies_live_data(_SETTINGS, _BEARS, _DENIAL)


@pytest.mark.asyncio
async def test_the_check_waits_no_longer_than_its_cap() -> None:
    """Review (2026-11-11): the client's timeout bounds each phase of the request, not the
    call, so a slow answer could hold the finished reply past the cap."""

    async def slow(*_args: Any, **_kwargs: Any) -> DeciderReply:
        await asyncio.sleep(5)
        return DeciderReply(answers={"denies": DeciderAnswer(type="noul", noul=0.9)})

    started = time.monotonic()
    with (
        patch("app.gateways.decider_gateway.decide", slow),
        patch.object(live_denial, "_CHECK_SECONDS", 0.05),
    ):
        assert not await live_denial.denies_live_data(_SETTINGS, _BEARS, _DENIAL)
    assert time.monotonic() - started < 1


@pytest.mark.asyncio
async def test_the_check_reads_the_message_and_both_ends_of_a_long_reply() -> None:
    """A denial leads the answer or closes it as a note; a long list's middle is the list."""
    check = _check(0.05)
    reply = "I can't check live data. " + "An item of the list. " * 200 + "Note: check ESPN."
    with patch("app.gateways.decider_gateway.decide", check):
        await live_denial.denies_live_data(_SETTINGS, "did the bears win", reply)
        assert not await live_denial.denies_live_data(_SETTINGS, "hi", "  ")
    check.assert_awaited_once()
    assert check.await_args is not None
    kwargs = check.await_args.kwargs
    assert kwargs["state"].startswith("The user's message: did the bears win\n\n")
    assert "I can't check live data." in kwargs["state"]
    assert kwargs["state"].endswith("Note: check ESPN.")
    assert len(kwargs["state"]) < 2200
    assert list(kwargs["questions"]) == ["denies"]


def _retry_context(
    content: str = _BEARS, tool: dict[str, Any] | None = None, *, nearly_live: bool = False
) -> StreamContext:
    ctx = _context(content)
    ctx.denial_retry_tools = [tool] if tool else []
    # The turn's read called the answer settled, close to live or not.
    ctx.live_read = _read(False, odds=0.2 if nearly_live else 0.02)  # type: ignore[assignment]
    return ctx


@pytest.mark.parametrize(("nearly_live", "requires"), [(True, "web_search"), (False, None)])
@pytest.mark.asyncio
async def test_a_denial_is_asked_again_with_search(
    web_search_tool: dict[str, Any], denial_check: AsyncMock, nearly_live: bool, requires: Any
) -> None:
    """Live (2026-10-25): no tool was offered, and the reply said it couldn't check. A read
    close to live makes the second call search, so its answer has results to give (Pro
    phone test, 2026-11-11); further off it is offered the search and its model decides: a
    search sends the conversation's words to the web (review). Both are told they can: a
    provider that ignores the tool choice would otherwise deny again (review, 2026-11-11)."""
    ctx = _retry_context(tool=web_search_tool, nearly_live=nearly_live)
    await asyncio.sleep(0)  # the read has answered by the reply's first call
    statuses: list[str] = []

    async def on_status(phase: str, _detail: str | None = None, **_kwargs: Any) -> None:
        statuses.append(phase)

    llm, seen = _model(([_DENIAL], []), ([], [_SEARCH_CALL]), ([_ANSWER], []))
    accum = StreamAccum()
    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        streamed = await _reply(ctx, llm, accum=accum, on_status=on_status)

    assert accum.reply_text() == _ANSWER
    assert accum.retracted == _DENIAL
    assert [call["tools"] for call in seen] == [None, [web_search_tool], None]
    assert [call["require_tool"] for call in seen] == [None, requires, None]
    assert any(DENIAL_RETRY_NOTE in str(m.get("content")) for m in seen[1]["messages"])
    assert not any(DENIAL_RETRY_NOTE in str(m.get("content")) for m in seen[0]["messages"])
    assert [hit.url for hit in ctx.search_sources] == [_HIT.url]
    # The phone takes the denial down; a client that keeps it gets a break before the answer.
    assert statuses[:2] == ["composing", "retract"]
    assert streamed == f"{_DENIAL}\n\n{_ANSWER}"
    denial_check.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_stop_while_the_check_runs_keeps_the_reply(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    """The check takes about 0.3 s after the reply streamed: a Stop in it is a Stop."""
    ctx = _retry_context(tool=web_search_tool)
    llm, seen = _model(([_DENIAL], []), (["never asked"], []))
    accum = StreamAccum()
    await _reply(ctx, llm, accum=accum, should_cancel=lambda: denial_check.await_count > 0)
    assert len(seen) == 1 and accum.was_cancelled
    assert accum.reply_text() == _DENIAL and not accum.retracted


def _follow_a_draft(ctx: StreamContext) -> None:
    ctx.recent_messages = [
        SimpleNamespace(role="user", content="write an email to my landlord about rent"),
        SimpleNamespace(role="assistant", content=_EMAIL_DRAFT),
    ]
    ctx.user_message_content = "make it shorter"


def _set_worked(ctx: StreamContext) -> None:
    from app.modules.chat.worked_render import WorkedLayout

    ctx.worked = WorkedLayout()


@pytest.mark.parametrize(
    "turn",
    [
        lambda ctx: setattr(ctx, "verified_subject", object()),
        lambda ctx: setattr(ctx, "money", object()),
        _set_worked,
        lambda ctx: setattr(ctx, "after_card", True),
        lambda ctx: setattr(ctx, "lightweight_turn", True),
        lambda ctx: setattr(
            ctx, "recent_messages", [SimpleNamespace(role="assistant", content=_LESSON_STEP)]
        ),
        lambda ctx: setattr(ctx, "user_message_content", "Text my coach I can't check the score"),
        lambda ctx: setattr(ctx, "user_message_content", "Translate to Spanish: I can't check it"),
        _follow_a_draft,
    ],
    ids=[
        "verified",
        "money",
        "worked",
        "after card",
        "small talk",
        "lesson",
        "draft",
        "translation",
        "draft follow-up",
    ],
)
@pytest.mark.asyncio
async def test_a_turn_whose_denial_is_no_live_fact_is_never_checked(
    web_search_tool: dict[str, Any], denial_check: AsyncMock, turn: Any
) -> None:
    """Review (2026-11-11): the check ran on nearly every turn. Numbers a server path
    worked, a lesson's step, a card's answer and the user's own words to send hold no claim
    a search could fix; they pay no second Decider call and wait for none."""
    ctx = _retry_context(tool=web_search_tool)
    turn(ctx)
    llm, seen = _model(([_DENIAL], []), (["never asked"], []))
    assert await _reply(ctx, llm) == _DENIAL
    assert len(seen) == 1
    denial_check.assert_not_awaited()


def test_a_regenerated_answer_to_a_draft_question_is_never_checked() -> None:
    """A regenerate keeps its message in the window the turn reads (review, 2026-11-11):
    read with it, the answer to "What should it say?" was no draft's, and its reply was
    checked. The turn's own test of a draft follow-up leaves it out."""
    ctx = _context("the heater broke last night")
    asked = [
        SimpleNamespace(role="user", content="write a message to my landlord"),
        SimpleNamespace(role="assistant", content="Sure. What should it say?"),
    ]
    ctx.recent_messages = [*asked, SimpleNamespace(role="user", content=ctx.user_message_content)]
    assert not live_denial.may_check(ctx)
    ctx.recent_messages = asked
    assert not live_denial.may_check(ctx)


@pytest.mark.asyncio
async def test_a_denial_then_text_before_the_search_both_give_way(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    ctx = _retry_context(tool=web_search_tool)
    llm, _seen = _model(([_DENIAL], []), (["Let me look."], [_SEARCH_CALL]), ([_ANSWER], []))
    accum = StreamAccum()
    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        await _reply(ctx, llm, accum=accum)

    assert accum.reply_text() == _ANSWER
    # Both were drawn, so a stop's count of drawn text takes both off.
    assert accum.retracted == f"{_DENIAL}\n\nLet me look."


@pytest.mark.asyncio
async def test_an_answer_after_a_recall_round_is_never_asked_again(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    """Review (2026-11-11): the retry stayed armed through a ``recall_chats`` round, so the
    answer after it could be retracted and searched, with earlier-chat snippets in the
    prompt a query could draw from. A tool round's answer has what it asked for."""
    ctx = _retry_context(tool=web_search_tool)
    ctx.reply_tools = [{"type": "function", "function": {"name": "recall_chats"}}]
    recall = {
        "id": "call_r",
        "type": "function",
        "function": {"name": "recall_chats", "arguments": '{"query": "the bears"}'},
    }
    llm, seen = _model(([], [recall]), ([_DENIAL], []), (["never asked"], []))
    with patch("app.modules.chat.tool_loop.reply_calls.answer_into_turn", AsyncMock()):
        assert await _reply(ctx, llm) == _DENIAL
    assert len(seen) == 2
    denial_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_reply_the_check_passes_is_not_asked_again(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    """Something private the app cannot see is no live fact a search finds."""
    ctx = _retry_context("what's my heart rate right now", web_search_tool)
    watch = "I can't access real-time data from your watch."
    llm, seen = _model(([watch], []), (["never asked"], []))
    assert await _reply(ctx, llm) == watch
    assert len(seen) == 1
    denial_check.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_retry_without_the_offer_or_for_a_clock_denial(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    llm, seen = _model(([_DENIAL], []), (["never asked"], []))
    assert await _reply(_retry_context(), llm) == _DENIAL
    assert len(seen) == 1
    clock = "I don't have access to real-time data, so I can't tell you the current time."
    llm, seen = _model(([clock], []), (["never asked"], []))
    assert await _reply(_retry_context("what time is it", web_search_tool), llm) == clock
    assert len(seen) == 1
    # Small talk asks nothing live.
    small_talk = _retry_context("thanks!", web_search_tool)
    small_talk.lightweight_turn = True
    llm, seen = _model(([_DENIAL], []), (["never asked"], []))
    assert await _reply(small_talk, llm) == _DENIAL
    # None of them asks the check: nothing to offer, the clock is the app's, a greeting.
    denial_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_stop_during_the_retry_saves_the_denial_the_phone_puts_back(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    """The phone took the denial down; a Stop with nothing in its place puts it back
    (``chatTurnState`` ``onStop``), so the server saves it and the phone's count is it."""
    ctx = _retry_context(tool=web_search_tool)
    llm, seen = _model(([_DENIAL], []), (["never drawn"], []))
    accum = StreamAccum()
    await _reply(ctx, llm, accum=accum, should_cancel=lambda: len(seen) > 1)
    assert accum.was_cancelled and accum.restored
    assert accum.reply_text(len(_DENIAL)) == _DENIAL


@pytest.mark.asyncio
async def test_a_stop_before_the_answer_saves_the_text_the_phone_still_shows(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    """Review (2026-11-11): the retry wrote "Let me look." and searched, and the user
    stopped before its answer. The phone took the denial down and still shows "Let me
    look."; the server put both back and saved the denial the phone no longer showed."""
    ctx = _retry_context(tool=web_search_tool)
    llm, seen = _model(([_DENIAL], []), (["Let me look."], [_SEARCH_CALL]), (["never"], []))
    accum = StreamAccum()
    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        await _reply(ctx, llm, accum=accum, should_cancel=lambda: len(seen) > 2)
    assert accum.was_cancelled and accum.restored
    drawn = len(_DENIAL) + len("\n\nLet me look.")
    assert accum.reply_text(drawn) == "Let me look."
    # Done carries it: the denial is still taken back.
    assert accum.retracted == _DENIAL


@pytest.mark.asyncio
async def test_a_failure_during_the_retry_keeps_the_denial_and_done_carries_it(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    """Review (2026-11-11): a provider failure in the retry saved the denial the phone had
    taken down, and done, which ends the turn as interrupted, said nothing of it: the phone
    drew an empty reply and a reload the denial."""
    from app.gateways.litellm_gateway import ModelUnavailableError
    from app.modules.chat.stream_pipeline import stream_and_finalize
    from app.modules.chat.turn_outcome import TurnOutcome

    ctx = _retry_context(tool=web_search_tool)
    first = {"done": False}

    async def stream_chat_completion(**kwargs: Any) -> AsyncIterator[str]:
        if first["done"]:
            raise ModelUnavailableError("down", failed_alias="free-chat")
        first["done"] = True
        yield _DENIAL

    async def enriched(*_args: Any, **kwargs: Any) -> str:
        return str(kwargs["assistant_text"])

    saved = AsyncMock()
    outcome = TurnOutcome()
    llm = SimpleNamespace(stream_chat_completion=stream_chat_completion)
    with (
        patch("app.modules.chat.stream_pipeline.run_tool_loop_path", AsyncMock()),
        patch("app.modules.chat.stream_pipeline.enrich_final_content", enriched),
        patch("app.modules.chat.stream_pipeline.register_and_enqueue_finalize", saved),
    ):
        streamed = [
            token
            async for token in stream_and_finalize(
                turn_deps(llm=llm),
                redis_mock(),
                _SETTINGS,
                ctx,
                should_cancel=None,
                outcome=outcome,
            )
        ]
    assert streamed == [_DENIAL]
    assert saved.await_args is not None and saved.await_args.kwargs["assistant_text"] == _DENIAL
    assert outcome.completion == "interrupted"
    assert outcome.final_content == _DENIAL


def test_a_stop_after_a_retraction_cuts_the_answer_where_the_phone_did() -> None:
    accum = StreamAccum(parts=[_DENIAL], shown=[_DENIAL])
    accum.retract(0, 0)
    accum.parts.append("\n\nThe Bears beat")
    accum.shown.append("\n\nThe Bears beat")
    accum.mark_user_stop()
    drawn = len(_DENIAL) + len("\n\nThe Bears")
    assert accum.reply_text(drawn) == "The Bears"


@pytest.mark.parametrize(
    ("taken", "drawn", "saved"),
    [
        # The answer's first words were on their way at the Stop: the phone put the denial
        # back, and the server cut the answer to nothing and saved none (review, 2026-11-11).
        ([_DENIAL], len(_DENIAL), _DENIAL),
        # The phone drew the text before the search, not the answer after it.
        ([_DENIAL, "\n\nLet me look."], len(_DENIAL) + len("\n\nLet me look."), "Let me look."),
        (["Let me look."], len("Let me look."), "Let me look."),
    ],
)
def test_a_stop_before_the_answer_was_drawn_saves_what_the_phone_shows(
    taken: list[str], drawn: int, saved: str
) -> None:
    accum = StreamAccum()
    for text in taken:
        accum.parts.append(text)
        accum.shown.append(text)
        accum.retract(len(accum.parts) - 1, len(accum.shown) - 1)
    accum.parts.append("\n\nThe Bears beat")
    accum.shown.append("\n\nThe Bears beat")
    accum.mark_user_stop()
    assert accum.reply_text(drawn) == saved


@pytest.mark.asyncio
async def test_a_held_mark_of_the_denial_never_reaches_the_answer(
    web_search_tool: dict[str, Any], denial_check: AsyncMock
) -> None:
    ctx = _retry_context(tool=web_search_tool)
    llm, _seen = _model((["Sorry, I can't check live scores!"], []), (["The Bears won."], []))
    accum = StreamAccum()
    await _reply(ctx, llm, accum=accum)
    assert accum.reply_text() == "The Bears won."


def _read(
    live: bool | None, query: str = "", *, asked: bool = False, odds: float | None = None
) -> asyncio.Future[Any]:
    from app.modules.chat.turn_decision import TurnDecision

    async def done() -> TurnDecision | None:
        if live is None:
            return None
        return TurnDecision(live=live, query=query, asked=asked, live_odds=odds)

    return asyncio.ensure_future(done())


# A settled read takes the tool away (``test_a_settled_read_takes_the_search_tool_off_the_reply``).
@pytest.mark.parametrize(("live", "requires"), [(True, "web_search"), (None, None)])
@pytest.mark.asyncio
async def test_a_live_read_without_a_query_makes_the_reply_search_first(
    web_search_tool: dict[str, Any], live: bool | None, requires: str | None
) -> None:
    """The model read beside the prep said the answer depends on facts that change: the
    reply's call must search, whatever its model would have chosen."""
    ctx = _context("who won the last world cup")
    ctx.live_read = _read(live)  # type: ignore[assignment]
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=None, should_cancel=None
    )
    assert ctx.reply_tools == [web_search_tool]
    assert ctx.reply_requires == requires


@pytest.mark.parametrize(("live", "offered"), [(False, False), (None, True)])
@pytest.mark.asyncio
async def test_a_settled_read_takes_the_search_tool_off_the_reply(
    web_search_tool: dict[str, Any], live: bool | None, offered: bool
) -> None:
    """One decider: told the read found nothing that changes and still offered the tool,
    GPT-6 Luna searched how-tos and the way to a place the chat had named (2026-11-09).
    A read with no answer in time leaves the tool to the reply's model."""
    ctx = _context("how do I reset my AirPods")
    ctx.live_read = _read(live)  # type: ignore[assignment]
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=None, should_cancel=None
    )
    assert ctx.reply_tools == ([web_search_tool] if offered else [])
    assert ctx.reply_requires is None
    assert ctx.prompt_messages == [{"role": "user", "content": "how do I reset my AirPods"}]


@pytest.mark.parametrize(
    ("live", "odds", "retry", "requires"),
    [
        # Settled: a reply that then denies live facts is asked again, offered the search.
        (False, 0.05, True, None),
        # Settled, but close to live ("Top 5 universities in Ethiopia" read 0.15): it must.
        (False, 0.2, True, "web_search"),
        # The text read gives no odds: offered.
        (False, None, True, None),
        # No read in time: the reply held the search itself, and nothing is checked.
        (None, None, False, None),
    ],
)
@pytest.mark.asyncio
async def test_only_a_settled_read_lets_a_denial_be_asked_again(
    web_search_tool: dict[str, Any],
    live: bool | None,
    odds: float | None,
    retry: bool,
    requires: Any,
) -> None:
    ctx = _context("Top 5 universities in Ethiopia")
    ctx.live_read = _read(live, odds=odds)  # type: ignore[assignment]
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=None, should_cancel=None
    )
    assert ctx.denial_retry_tools == ([web_search_tool] if retry else [])
    read = answered_read(ctx)
    assert (read is not None and read.nearly_live) is (requires is not None)


@pytest.mark.asyncio
async def test_a_turn_the_read_never_saw_is_never_checked() -> None:
    """Small talk carries no search tool, so its read is never waited for: no retry."""
    ctx = _context("thanks!")
    ctx.lightweight_turn = True
    ctx.live_read = _read(False, odds=0.01)  # type: ignore[assignment]
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=None, should_cancel=None
    )
    assert ctx.denial_retry_tools == []


def test_a_settled_read_keeps_recall_chats() -> None:
    from app.modules.chat.tool_loop.reply_calls import _without_search

    recall = {"type": "function", "function": {"name": "recall_chats"}}
    search = {"type": "function", "function": {"name": "web_search"}}
    assert _without_search([search, recall]) == [recall]


@pytest.mark.parametrize(("live", "asked"), [(True, False), (False, True)])
@pytest.mark.asyncio
async def test_a_live_read_searches_its_query_before_the_reply(
    web_search_tool: dict[str, Any], live: bool, asked: bool
) -> None:
    """One model call answers: the read's query is searched in the prep, and the reply
    reads the results with no second search on offer. So is a search the user asked for,
    whatever the topic."""
    ctx = _context("who won the last world cup")
    ctx.live_read = _read(live, "2026 FIFA World Cup winner", asked=asked)  # type: ignore[assignment]
    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    search = AsyncMock(return_value=([_HIT], ["q"]))
    statuses: list[tuple[str, str | None]] = []

    async def on_status(
        phase: str, detail: str | None = None, *, elapsed_ms: int | None = None
    ) -> None:
        statuses.append((phase, detail))

    with patch("app.modules.web_search.tool.run_cached_search", search):
        await run_tool_loop_path(
            deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=on_status, should_cancel=None
        )
    # The user sees what is searched while it runs, never a blank screen.
    assert ("searching", "2026 FIFA World Cup winner") in statuses
    assert search.await_args is not None and search.await_args.args[1][0].startswith(
        "2026 FIFA World Cup winner"
    )
    assert ctx.reply_tools == []
    assert ctx.reply_requires is None
    assert [hit.url for hit in ctx.search_sources] == [_HIT.url]
    call_turn, result = ctx.prompt_messages[-2:]
    assert call_turn["tool_calls"][0]["function"]["name"] == "web_search"
    assert result["role"] == "tool" and _HIT.url in result["content"]


@pytest.mark.asyncio
async def test_a_read_still_running_shows_thinking(web_search_tool: dict[str, Any]) -> None:
    from app.modules.chat.turn_decision import TurnDecision

    async def slow() -> TurnDecision | None:
        await asyncio.sleep(0.05)
        return TurnDecision(live=False)

    ctx = _context("hello there")
    ctx.live_read = asyncio.ensure_future(slow())
    statuses: list[tuple[str, str | None]] = []

    async def on_status(
        phase: str, detail: str | None = None, *, elapsed_ms: int | None = None
    ) -> None:
        statuses.append((phase, detail))

    deps = turn_deps(quota={"global_spend_exceeded": AsyncMock(return_value=False)})
    await run_tool_loop_path(
        deps, redis_mock(), _SETTINGS, ctx, usage={}, on_status=on_status, should_cancel=None
    )
    assert statuses == [("thinking", None)]
    assert ctx.reply_requires is None


@pytest.mark.asyncio
async def test_only_the_first_call_must_search(web_search_tool: dict[str, Any]) -> None:
    ctx = _context("who won the last world cup")
    ctx.reply_tools = [web_search_tool]
    ctx.reply_requires = "web_search"
    llm, seen = _model(([], [_SEARCH_CALL]), (["Spain won it."], []))

    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        text = await _reply(ctx, llm)

    assert text == "Spain won it."
    assert seen[0]["require_tool"] == "web_search"
    assert seen[1]["require_tool"] is None
