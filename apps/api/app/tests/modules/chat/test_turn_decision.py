"""A model reads how to handle a message (``turn_decision``): live facts, subject, effort,
picture and follow-up."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.gateways.litellm_gateway import _call_kwargs
from app.gateways.stream_tool_calls import ToolOffer
from app.models import model_catalog
from app.modules.chat import decider_read, turn_decision
from app.modules.chat.turn_decision import TurnDecision
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings(web_search_enabled=True, mcp_tool_loop_enabled=True)
_STRUCTURED = "app.gateways.structured_completion.complete_structured"


@pytest.fixture(autouse=True)
def no_decider(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Decider gives no answer unless a test says so: the text read decides."""
    monkeypatch.setattr(decider_read, "decide_turn", AsyncMock(return_value=None))


@pytest.fixture(autouse=True)
def under_the_spend_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: object())
    monkeypatch.setattr("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False))


@pytest.mark.asyncio
async def test_no_read_past_the_spend_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True))
    ask = AsyncMock()
    with patch(_STRUCTURED, ask):
        assert (
            await turn_decision.read_decision(_SETTINGS, "who won the last world cup", earlier=[])
            is None
        )
    ask.assert_not_awaited()


@pytest.mark.parametrize("live", [True, False])
@pytest.mark.asyncio
async def test_the_read_is_the_models_answer(live: bool) -> None:
    ask = AsyncMock(return_value=TurnDecision(live=live))
    with patch(_STRUCTURED, ask):
        read = await turn_decision.read_decision(
            _SETTINGS, "who won the last world cup", earlier=[]
        )
    assert read is not None and read.live is live
    assert ask.await_args is not None
    messages = ask.await_args.kwargs["messages"]
    assert messages[0]["role"] == "system" and "Today is" in messages[0]["content"]
    assert messages[-1] == {
        "role": "user",
        "content": "The user's last message: who won the last world cup",
    }


@pytest.mark.asyncio
async def test_a_follow_up_is_read_with_the_turns_before_it_quoted() -> None:
    """After a chat about a MacBook Air's battery, "How much" was searched as an iPhone
    battery's cost when the read saw one reply; and given the chat as turns, a model
    answered the user instead of judging the message."""
    ask = AsyncMock(return_value=TurnDecision(live=True))
    recent = [
        SimpleNamespace(role="user", content="Macbook air"),
        SimpleNamespace(role="assistant", content="A MacBook Air has no fan."),
        SimpleNamespace(role="user", content="Can I replace the battery myself?"),
        SimpleNamespace(role="assistant", content="You can, but it's fiddly."),
    ]
    with patch(_STRUCTURED, ask):
        await turn_decision.read_decision(
            _SETTINGS, "How much", earlier=turn_decision.earlier_turns(recent)
        )
    assert ask.await_args is not None
    messages = ask.await_args.kwargs["messages"]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[1]["content"] == (
        "Earlier turns:\nUser: Macbook air\nAssistant: A MacBook Air has no fan.\n"
        "User: Can I replace the battery myself?\nAssistant: You can, but it's fiddly.\n\n"
        "The user's last message: How much"
    )


def test_the_read_sees_the_last_two_exchanges_each_cut_short() -> None:
    recent = [
        SimpleNamespace(role="user", content="first"),
        SimpleNamespace(role="assistant", content="first reply"),
        SimpleNamespace(role="system", content="a note"),
        SimpleNamespace(role="user", content="second"),
        SimpleNamespace(role="assistant", content="x" * 1000),
        SimpleNamespace(role="user", content="third"),
        SimpleNamespace(role="assistant", content="   "),
        SimpleNamespace(role="assistant", content="third reply"),
    ]
    assert turn_decision.earlier_turns(recent) == [
        ("user", "second"),
        ("assistant", "x" * 400),
        ("user", "third"),
        ("assistant", "third reply"),
    ]
    assert turn_decision.earlier_turns(None) == []


@pytest.mark.parametrize(
    "kind",
    [
        # 2026-11-09, one chat: each of these was searched before a reply that needed none.
        "whether to repair, replace or buy something",
        "steps, settings and checks on a phone",
        "where the user is",
        "getting from the user to a place the conversation already named",
        # And what searches whatever the topic: the read's ``asked``.
        "asked is true when the user's last message asks you to search the web",
        # Never the user's own words sent to the web: their chats and memory are here.
        "a search of their own chats, memory, notes, to-dos or files is not asked",
        # Whether to think first (``model_routing.thinking``), and what never needs it.
        "think is true when a careful answer must be reasoned out before it is written",
        "a single equation or expression to solve, differentiate or simplify",
    ],
)
def test_the_reads_instructions_name_each_kind(kind: str) -> None:
    assert kind in turn_decision.decision_messages("hi", [])[0]["content"]


@pytest.mark.parametrize(
    ("live", "asked", "searches"),
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_a_live_answer_or_an_asked_search_searches(live: bool, asked: bool, searches: bool) -> None:
    assert TurnDecision(live=live, asked=asked).searches is searches


@pytest.mark.parametrize("answer", [None, RuntimeError("provider down")])
@pytest.mark.asyncio
async def test_no_read_is_no_answer(answer: Any) -> None:
    ask = (
        AsyncMock(side_effect=answer)
        if isinstance(answer, Exception)
        else AsyncMock(return_value=None)
    )
    with patch(_STRUCTURED, ask):
        assert await turn_decision.read_decision(_SETTINGS, "hi", earlier=[]) is None


@pytest.mark.asyncio
async def test_an_empty_message_is_never_read() -> None:
    ask = AsyncMock()
    with patch(_STRUCTURED, ask):
        assert await turn_decision.read_decision(_SETTINGS, "  ", earlier=[]) is None
    ask.assert_not_awaited()


def test_no_read_starts_while_it_is_off() -> None:
    settings = isolated_settings(live_read_enabled=False)
    assert (
        turn_decision.start_turn_decision(settings, "who won the last world cup", recent=None)
        is None
    )


@pytest.mark.asyncio
async def test_search_off_still_reads_the_turn() -> None:
    """The lane and the thinking come from the read too, so web search off keeps it."""
    ask = AsyncMock(return_value=TurnDecision(live=False))
    settings = isolated_settings(web_search_enabled=False, live_read_enabled=True)
    with patch(_STRUCTURED, ask):
        task = turn_decision.start_turn_decision(settings, "solve 2x + 5 = 17", recent=None)
        assert task is not None
        assert await task is not None


@pytest.mark.asyncio
async def test_a_slow_read_counts_as_none() -> None:
    async def slow() -> TurnDecision | None:
        await asyncio.sleep(5)
        return TurnDecision(live=True)

    settings = isolated_settings(live_read_wait_seconds=0.01)
    assert await turn_decision.turn_decision_result(asyncio.ensure_future(slow()), settings) is None
    assert await turn_decision.turn_decision_result(None, settings) is None


@pytest.mark.parametrize("live", [True, False])
@pytest.mark.asyncio
async def test_the_reads_answer_is_handed_on_live_or_not(live: bool) -> None:
    """A settled answer is handed on too: the reply is told it (``reply_calls``)."""

    async def read() -> TurnDecision | None:
        return TurnDecision(live=live, query="world cup winner" if live else "")

    found = await turn_decision.turn_decision_result(asyncio.ensure_future(read()), _SETTINGS)
    assert found is not None and found.live is live


def _tools(*names: str) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": name, "parameters": {}}} for name in names]


@pytest.mark.parametrize(
    ("require", "choice"),
    [
        ("web_search", {"type": "function", "function": {"name": "web_search"}}),
        (None, "auto"),
        # A tool the call does not carry is never required of it.
        ("generate_image", "auto"),
    ],
)
def test_a_required_tool_is_named_to_the_provider(require: str | None, choice: Any) -> None:
    kwargs, calls = _call_kwargs(
        isolated_settings(openrouter_api_key="sk-or-test"),
        model_catalog.get("qwen-3.7-flash"),
        False,
        ToolOffer(_tools("web_search", "recall_chats"), require),
    )
    assert calls is not None
    assert kwargs["tool_choice"] == choice


@pytest.mark.parametrize(
    ("think", "hard", "effort"),
    [(False, False, "none"), (False, True, "none"), (True, False, "low"), (True, True, "high")],
)
def test_the_effort_comes_from_think_and_hard(think: bool, hard: bool, effort: str) -> None:
    read = TurnDecision.model_validate({"live": False, "think": think, "hard": hard})
    assert read.effort == effort


def test_a_read_with_no_think_has_no_effort() -> None:
    """The word rules decide the level then (``decided_turn``)."""
    assert TurnDecision(live=False).effort is None


def test_an_odd_field_drops_only_that_field() -> None:
    """A subject the schema does not name (biology) leaves the search and effort read."""
    read = TurnDecision.model_validate(
        {"live": True, "query": "q", "subject": "biology", "think": True, "picture": "map"}
    )
    assert (read.live, read.subject, read.effort, read.picture) == (True, None, "low", None)


@pytest.mark.asyncio
async def test_a_message_with_nothing_before_it_follows_nothing() -> None:
    """Asked "Solve 3x + 7 = 22" alone, the read called it a follow-up asking to solve."""
    ask = AsyncMock(return_value=TurnDecision(live=False, follow="solve"))
    with patch(_STRUCTURED, ask):
        read = await turn_decision.read_decision(_SETTINGS, "Solve 3x + 7 = 22", earlier=[])
    assert read is not None and read.follow == "none"
    ask = AsyncMock(return_value=TurnDecision(live=False, follow="solve"))
    with patch(_STRUCTURED, ask):
        read = await turn_decision.read_decision(
            _SETTINGS, "Do it", earlier=[("assistant", "A cart of 12 kg ... What is a?")]
        )
    assert read is not None and read.follow == "solve"


@pytest.mark.parametrize(
    "kind",
    [
        "subject is what the message is about",
        "gas laws and heat are physics",
        "hard is true when the reasoning is the work itself",
        "picture is what the message asks to see",
        "A map is none",
        "follow is how the message relates to the earlier turns",
    ],
)
def test_the_instructions_name_each_decision(kind: str) -> None:
    assert kind in turn_decision.decision_messages("hi", [])[0]["content"]


@pytest.mark.asyncio
async def test_a_refused_read_asks_the_backup_within_the_budget() -> None:
    """The read's model was rate-limited upstream on 15-40% of calls (2026-11-10): a refusal
    comes back at once, and the backup lane reads the message inside the same wait."""
    from app.models.routing_lanes import ROUTING

    answer = TurnDecision(live=False, subject="maths")
    ask = AsyncMock(side_effect=[None, answer])
    with patch(_STRUCTURED, ask):
        read = await turn_decision.read_decision(_SETTINGS, "solve 2x + 5 = 17", earlier=[])
    assert read is not None and read.subject == "maths"
    aliases = [call.kwargs["model_alias"] for call in ask.await_args_list]
    assert aliases == [ROUTING.live_read, ROUTING.live_read_backup]
    assert ask.await_args_list[1].kwargs["timeout_seconds"] <= _SETTINGS.live_read_timeout_seconds


@pytest.mark.asyncio
async def test_a_read_with_too_little_budget_left_asks_no_backup() -> None:
    settings = isolated_settings(live_read_timeout_seconds=0.5)
    ask = AsyncMock(return_value=None)
    with patch(_STRUCTURED, ask):
        assert await turn_decision.read_decision(settings, "hi", earlier=[]) is None
    assert ask.await_count == 1


@pytest.mark.asyncio
async def test_a_measured_model_is_asked_alone() -> None:
    ask = AsyncMock(return_value=None)
    with patch(_STRUCTURED, ask):
        await turn_decision.read_decision(_SETTINGS, "hi", earlier=[], model_alias="gpt-6-luna")
    assert ask.await_count == 1


def _fields(**over: Any) -> dict[str, Any]:
    base = {
        "subject": "everyday",
        "think": False,
        "hard": False,
        "picture": "none",
        "follow": "none",
        "live": False,
        "asked": False,
    }
    return {**base, **over}


@pytest.mark.asyncio
async def test_the_deciders_answer_is_the_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """It read the decider corpus better than the text read at a third of its time."""
    monkeypatch.setattr(
        decider_read, "decide_turn", AsyncMock(return_value=_fields(subject="physics"))
    )
    ask = AsyncMock(return_value=TurnDecision(live=False, subject="everyday"))
    with patch(_STRUCTURED, ask):
        read = await turn_decision.read_decision(_SETTINGS, "Draw the circuit", earlier=[])
    assert read is not None and (read.subject, read.effort, read.searches) == (
        "physics",
        "none",
        False,
    )


@pytest.mark.asyncio
async def test_a_live_decision_takes_its_query_from_the_text_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Decider writes no text: the search query is the text read's, begun beside it."""
    monkeypatch.setattr(decider_read, "decide_turn", AsyncMock(return_value=_fields(live=True)))
    ask = AsyncMock(return_value=TurnDecision(live=True, query="World Cup winner"))
    with patch(_STRUCTURED, ask):
        read = await turn_decision.read_decision(_SETTINGS, "who won the world cup", earlier=[])
    assert read is not None and read.searches and read.query == "World Cup winner"


@pytest.mark.parametrize(
    ("subject", "think", "hard", "effort"),
    [
        # STEM thinks only when hard: easy textbook problems were read "low" (2026-11-10).
        ("physics", 0.9, 0.5, "none"),
        ("maths", 0.9, 0.8, "high"),
        ("everyday", 0.9, 0.5, "low"),
        ("everyday", 0.9, 0.97, "high"),
        ("everyday", 0.2, 0.97, "none"),
    ],
)
def test_the_deciders_probabilities_set_the_effort(
    subject: str, think: float, hard: float, effort: str
) -> None:
    answers = {
        "subject": {"choice": subject},
        "think": {"noul": think},
        "hard": {"noul": hard},
        "picture": {"choice": "none"},
        "follow": {"choice": "draw"},
        "live": {"noul": 0.1},
        "asked": {"noul": 0.1},
    }
    fields = decider_read.decision_fields(answers, has_earlier=True)
    assert fields is not None
    read = TurnDecision(**fields)
    assert (read.effort, read.follow) == (effort, "draw")
    assert decider_read.decision_fields(answers, has_earlier=False)["follow"] == "none"  # type: ignore[index]
    assert decider_read.decision_fields({}, has_earlier=False) is None
