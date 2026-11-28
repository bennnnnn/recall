"""Each recommended name written as a link, asked for when the turn's read says the answer
names things to look up (``chat.names_turn``), never by a word rule such as "near me"."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.modules.chat.decided_turn import decide_from_the_read
from app.modules.chat.decider_read import LAYOUT_QUESTIONS, NAMES_AT, decision_fields
from app.modules.chat.names_turn import link_the_names
from app.modules.chat.prompt_constants.format import NAME_LINK_NOTE
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings()


def _read(names: bool | None) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": "everyday", "think": False, "names": names}
    )


def _turn(read: TurnDecision | None, *, steps_open: bool = True, **fields: Any) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "which museums should I visit in Paris?"},
        ],
        run_title=False,
        user_message_content="which museums should I visit in Paris?",
        reserved_tokens=100,
        max_output_tokens=100,
    )
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result(read)
    ctx.live_read = future  # type: ignore[assignment]
    ctx.steps_open = steps_open
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


@pytest.mark.asyncio
async def test_an_answer_that_recommends_names_asks_for_their_links() -> None:
    trace = begin_turn_trace("new")
    ctx = _turn(_read(True))
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.prompt_messages[-2]["content"] == NAME_LINK_NOTE
    assert ctx.prompt_messages[-1]["role"] == "user"
    assert "read.names" in trace.prompt_rules


@pytest.mark.parametrize("names", [False, None], ids=["history", "no-answer"])
@pytest.mark.asyncio
async def test_no_names_or_no_answer_leave_the_rules_alone(names: bool | None) -> None:
    trace = begin_turn_trace("new")
    ctx = _turn(_read(names))
    before = list(ctx.prompt_messages)
    await decide_from_the_read(ctx, _SETTINGS)
    assert NAME_LINK_NOTE not in [m["content"] for m in ctx.prompt_messages]
    assert "read.names" not in trace.prompt_rules
    assert ctx.prompt_messages[-1] == before[-1]


@pytest.mark.parametrize(
    "fields",
    [{"instant_reply": "Hi!"}, {"money": object()}, {"verified_subject": "math"}],
    ids=["instant", "money-card", "solved"],
)
@pytest.mark.asyncio
async def test_a_turn_the_server_answered_gets_no_note(fields: dict[str, Any]) -> None:
    begin_turn_trace("new")
    ctx = _turn(_read(True), **fields)
    link_the_names(ctx, _read(True))
    assert NAME_LINK_NOTE not in [m["content"] for m in ctx.prompt_messages]


@pytest.mark.asyncio
async def test_a_ranking_layout_takes_the_note_too() -> None:
    """ "best restaurants in San Francisco" asks for a ranking, which its words lay out."""
    begin_turn_trace("new")
    ctx = _turn(_read(True), steps_open=False)
    link_the_names(ctx, _read(True))
    assert ctx.prompt_messages[-2]["content"] == NAME_LINK_NOTE


def test_the_names_answer_rides_the_steps_call() -> None:
    assert set(LAYOUT_QUESTIONS) == {"steps", "names"}
    base: dict[str, Any] = {
        "subject": {"choice": "everyday"},
        "think": {"noul": 0.0},
        "hard": {"noul": 0.0},
        "live": {"noul": 0.0},
        "asked": {"noul": 0.0},
    }
    assert (decision_fields(base, has_earlier=False) or {})["names"] is None
    picks = {**base, "names": {"noul": NAMES_AT + 0.1}}
    assert (decision_fields(picks, has_earlier=False) or {})["names"] is True
    told = {**base, "names": {"noul": NAMES_AT - 0.1}}
    assert (decision_fields(told, has_earlier=False) or {})["names"] is False
