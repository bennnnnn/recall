"""The ```steps card comes from the turn's read, never from "how to …" (``chat.steps_turn``).

"How to look handsome" got six independent tips in the arrows card, its reply opening "It's
a how-to" (the owner, 2026-11-27): a word rule gave every "how to …" the card, and the hint
named the turn in words the model repeated. The read now says whether the answer is one
procedure carried out in order; tips and ways keep the scan layout's numbered list.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.gateways import decider_gateway, llm_spend
from app.gateways.decider_gateway import DeciderReply
from app.modules.chat import decider_read, picture_ask, turn_decision
from app.modules.chat.decided_turn import decide_from_the_read
from app.modules.chat.prompt_constants.format import STEPS_FORMAT_HINT
from app.modules.chat.steps_turn import gives_the_steps_card, lay_out_the_steps
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings()


def _read(steps: bool | None, **fields: Any) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": "everyday", "think": False, "steps": steps, **fields}
    )


def _turn(read: TurnDecision | None, *, steps_open: bool = True, **fields: Any) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "how to tie a tie"},
        ],
        run_title=False,
        user_message_content="how to tie a tie",
        reserved_tokens=100,
        max_output_tokens=100,
    )
    try:
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    except RuntimeError:  # A sync test asks the card's rule alone, with no read to wait for.
        future = None  # type: ignore[assignment]
    else:
        future.set_result(read)
    ctx.live_read = future  # type: ignore[assignment]
    ctx.steps_open = steps_open
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


def _beside_the_message(ctx: StreamContext) -> str:
    return str(ctx.prompt_messages[-2]["content"])


@pytest.mark.asyncio
async def test_a_procedure_gets_the_card_beside_its_message() -> None:
    begin_turn_trace("new")
    ctx = _turn(_read(True))
    await decide_from_the_read(ctx, _SETTINGS)
    assert _beside_the_message(ctx) == STEPS_FORMAT_HINT
    assert ctx.prompt_messages[-1]["role"] == "user"


@pytest.mark.parametrize("steps", [False, None], ids=["ways", "no-answer"])
@pytest.mark.asyncio
async def test_tips_or_no_answer_keep_the_scan_layout(steps: bool | None) -> None:
    begin_turn_trace("new")
    ctx = _turn(_read(steps))
    await decide_from_the_read(ctx, _SETTINGS)
    assert all(STEPS_FORMAT_HINT not in str(m["content"]) for m in ctx.prompt_messages)


@pytest.mark.asyncio
async def test_no_read_at_all_keeps_the_scan_layout() -> None:
    begin_turn_trace("new")
    ctx = _turn(None)
    await decide_from_the_read(ctx, _SETTINGS)
    assert all(STEPS_FORMAT_HINT not in str(m["content"]) for m in ctx.prompt_messages)


@pytest.mark.parametrize(
    ("read", "fields"),
    [
        # Its words gave the reply a layout of their own (a comparison, a lesson, a draft).
        (_read(True), {"steps_open": False}),
        # A server path worked its numbers: the solve's or the money card's layout.
        (_read(True), {"verified_subject": "math"}),
        (_read(True), {"money": object()}),
        (_read(True), {"solver_unverified": True}),
        (_read(True), {"instant_reply": "Hi!"}),
        (_read(True, subject="money"), {}),
        (_read(True, work=True), {}),
        (_read(True, picture="diagram"), {}),
    ],
)
def test_a_turn_with_a_layout_of_its_own_gets_no_card(
    read: TurnDecision, fields: dict[str, Any]
) -> None:
    steps_open = fields.pop("steps_open", True)
    ctx = _turn(read, steps_open=steps_open, **fields)
    assert not gives_the_steps_card(ctx, read)
    before = list(ctx.prompt_messages)
    lay_out_the_steps(ctx, read)
    assert ctx.prompt_messages == before


def test_a_photo_above_the_steps_still_takes_the_card() -> None:
    read = _read(True, picture="photo")
    assert gives_the_steps_card(_turn(read), read)


@pytest.mark.asyncio
async def test_the_steps_question_is_its_own_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asked among the turn's questions it would move their measured answers (the Decider
    weighs a call's questions together): a call of its own, as the work question is."""
    asked: list[set[str]] = []
    turn = {
        "subject": {"type": "choice", "choice": "everyday"},
        "think": {"type": "noul", "noul": 0.1},
        "hard": {"type": "noul", "noul": 0.1},
        "picture": {"type": "choice", "choice": "none"},
        "follow": {"type": "choice", "choice": "none"},
        "live": {"type": "noul", "noul": 0.0},
        "asked": {"type": "noul", "noul": 0.0},
    }

    async def decide(_settings: Any, *, questions: dict[str, Any], **_: Any) -> DeciderReply:
        asked.append(set(questions))
        if "steps" in questions:
            answers = {"steps": {"type": "noul", "noul": 0.99}}
            return DeciderReply.model_validate({"answers": answers, "usage": {"cost": 0.0}})
        return DeciderReply.model_validate({"answers": turn, "usage": {"cost": 0.0}})

    monkeypatch.setattr(decider_gateway, "decide", decide)
    monkeypatch.setattr(llm_spend, "meter_reported_cost", lambda _alias, _cost: None)
    fields = await decider_read.decide_turn(
        _SETTINGS, "how to tie a tie", has_earlier=False, seconds=1.0, ask_steps=True
    )
    assert fields is not None and fields["steps"] is True
    assert {"steps"} in asked and "steps" not in decider_read.QUESTIONS
    fields = await decider_read.decide_turn(
        _SETTINGS, "how to tie a tie", has_earlier=False, seconds=1.0
    )
    assert fields is not None and fields["steps"] is None


@pytest.mark.parametrize(("odds", "card"), [(0.99, True), (0.46, False), (0.03, False)])
def test_the_card_is_given_at_the_measured_line(odds: float, card: bool) -> None:
    """0.46 was "how to pick a college major", the closest no on the steps-need corpus."""
    answers = {
        "subject": {"choice": "everyday"},
        "think": {"noul": 0.1},
        "hard": {"noul": 0.1},
        "live": {"noul": 0.0},
        "asked": {"noul": 0.0},
        "steps": {"noul": odds},
    }
    fields = decider_read.decision_fields(answers, has_earlier=False)
    assert fields is not None and fields["steps"] is card


@pytest.mark.asyncio
async def test_a_pending_read_is_waited_for_when_only_the_steps_are_at_stake() -> None:
    """Auto off, no search, no lesson: the card alone makes the turn wait for its read
    (``decided_turn._steps_at_stake``); left unwaited, a procedure lost its card."""
    begin_turn_trace("new")
    loop = asyncio.get_running_loop()
    ctx = _turn(None)
    pending: asyncio.Future[Any] = loop.create_future()
    loop.call_later(0.05, pending.set_result, _read(True))
    ctx.live_read = pending  # type: ignore[assignment]
    ctx.auto_routed = False
    await decide_from_the_read(ctx, _SETTINGS)
    assert _beside_the_message(ctx) == STEPS_FORMAT_HINT


@pytest.mark.asyncio
async def test_a_pending_read_is_not_waited_for_on_a_shaped_turn() -> None:
    begin_turn_trace("new")
    ctx = _turn(None, steps_open=False)
    pending: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    ctx.live_read = pending  # type: ignore[assignment]
    ctx.auto_routed = False
    await asyncio.wait_for(decide_from_the_read(ctx, _SETTINGS), 0.5)
    assert all(STEPS_FORMAT_HINT not in str(m["content"]) for m in ctx.prompt_messages)
    pending.cancel()


@pytest.fixture
def _reads(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """``read_decision`` with the Decider's call recorded and every other call faked."""
    from app.services import model_health

    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: object())
    monkeypatch.setattr("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False))
    breakers = model_health.Breakers(cooling=frozenset(), half_open=frozenset())
    monkeypatch.setattr(model_health, "read_breakers", AsyncMock(return_value=breakers))
    fields = {"subject": "everyday", "think": False, "hard": False, "live": False}
    decider = AsyncMock(return_value={**fields, "asked": False, "steps": True})
    monkeypatch.setattr(decider_read, "decide_turn", decider)
    monkeypatch.setattr(
        "app.gateways.structured_completion.complete_structured",
        AsyncMock(return_value=TurnDecision(live=False)),
    )
    return decider


@pytest.mark.parametrize(
    ("kwargs", "asked"),
    [
        ({}, True),
        # After a lesson's cards, a lesson step or a cut-off reply: its layout is that one's.
        ({"lesson": {"goes_on": {"type": "noul", "instructions": "next?"}}}, False),
        # The composer's picture check reads only the picture.
        ({"steps": False}, False),
    ],
)
@pytest.mark.asyncio
async def test_the_turns_read_asks_the_steps_question_only_where_it_counts(
    _reads: AsyncMock, kwargs: dict[str, Any], asked: bool
) -> None:
    read = await turn_decision.read_decision(_SETTINGS, "how to tie a tie", earlier=[], **kwargs)
    assert read is not None and read.steps is True
    assert _reads.await_args is not None
    assert _reads.await_args.kwargs["ask_steps"] is asked


@pytest.mark.asyncio
async def test_the_composers_picture_check_reads_no_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    start = MagicMock(return_value=None)
    monkeypatch.setattr(picture_ask, "start_turn_decision", start)
    assert await picture_ask.read_picture_ask(_SETTINGS, "draw a cat", []) is None
    assert start.call_args.kwargs["steps"] is False
