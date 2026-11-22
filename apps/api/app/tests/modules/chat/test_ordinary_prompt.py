"""Ordinary chat's shorter rules (``ordinary_prompt``): rendered for a turn whose words ask for
no shape of their own, and sent only when the turn's read calls it everyday chat."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.models.orm import User
from app.modules.chat.decided_turn import decide_from_the_read
from app.modules.chat.ordinary_prompt import OrdinaryPrompt, is_ordinary
from app.modules.chat.prompt_constants import (
    CLARIFICATION_HINT,
    CLARIFY_CARD_HINT,
    COPY_DELIVERABLE_HINT,
    FORMAT_CONTRACT,
    MATH_FENCE_SAFETY_HINT,
    NON_DRAFT_TURN_HINT,
    PRIVACY_HINT,
    UNIVERSAL_FORMAT_BASELINE,
)
from app.modules.chat.prompt_constants.format import ORDINARY_FORMAT_GUIDE
from app.modules.chat.prompt_constants.privacy import PRIVACY_CONTEXT_HINT
from app.modules.chat.prompt_format import _style_format_hints
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.tests.fakes import isolated_settings
from app.tests.modules.chat.test_prompt_golden import _CASES, _DEFAULTS, render, resolve

_SETTINGS = isolated_settings()
_FULL_ONLY = (
    FORMAT_CONTRACT,
    UNIVERSAL_FORMAT_BASELINE,
    COPY_DELIVERABLE_HINT,
    CLARIFICATION_HINT,
    PRIVACY_HINT,
    NON_DRAFT_TURN_HINT,
    MATH_FENCE_SAFETY_HINT,
)


def _hints(text: str, *, ordinary: bool) -> list[str]:
    return _style_format_hints(
        query_text=text,
        is_day_plan=False,
        minimal_personal_context=False,
        image_search_enabled=True,
        ordinary=ordinary,
    )


@pytest.mark.parametrize(
    "text",
    [
        "hey whats a good quick dinner idea",
        "how do I ask for a raise at my job?",
        "compare netflix hulu and disney plus in a table",
        "what is the best country",
    ],
)
def test_a_plain_turn_gets_the_short_guide_and_keeps_its_own_rules(text: str) -> None:
    full, ordinary = _hints(text, ordinary=False), _hints(text, ordinary=True)
    assert ORDINARY_FORMAT_GUIDE in ordinary and PRIVACY_CONTEXT_HINT in ordinary
    assert not any(hint in ordinary for hint in _FULL_ONLY)
    # What the turn's words asked for stays: its layout, the tap card, the photo.
    dropped = {*_FULL_ONLY, FORMAT_CONTRACT}
    assert [hint for hint in full if hint not in dropped] == [
        hint for hint in ordinary if hint not in {ORDINARY_FORMAT_GUIDE, PRIVACY_CONTEXT_HINT}
    ]
    assert sum(map(len, ordinary)) < sum(map(len, full)) / 2


def test_the_card_rule_stays_where_a_card_may_ask() -> None:
    assert CLARIFY_CARD_HINT in _hints("what is the best country", ordinary=True)


@pytest.mark.parametrize(
    "text",
    [
        "write an email to my landlord about the broken heater",
        "teach me python",
        "make a bar chart of the population of the 5 largest countries",
        "draw a flowchart of how a bill becomes law in the US",
        "solve 2x + 5 = 17",
        "what can you do",
        "explain this code:\n```python\ndef f(x):\n    return x + 1\n```",
        "Quiz me on the planets of the solar system",
        "proofread this: their going to the store",
    ],
)
def test_a_turn_with_a_shape_of_its_own_keeps_every_rule(text: str) -> None:
    assert _hints(text, ordinary=True) == _hints(text, ordinary=False)


def test_the_compact_message_takes_the_place_of_the_full_one() -> None:
    swap = OrdinaryPrompt(full="rules", compact="short")
    messages = [
        {"role": "system", "content": "stable"},
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "rules"},
    ]
    assert swap.apply(messages) == [
        {"role": "system", "content": "stable"},
        {"role": "system", "content": "short"},
        {"role": "user", "content": "rules"},
    ]
    # Changed since it was built: nothing to swap.
    assert swap.apply([{"role": "system", "content": "rules and a note"}]) is None


def _read(**fields: Any) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": "everyday", "think": False, **fields}
    )


@pytest.mark.parametrize(
    ("read", "ordinary"),
    [
        (_read(), True),
        (_read(think=True), True),
        (_read(picture="photo"), True),
        (_read(work=False), True),
        (_read(think=True, hard=True), False),
        (_read(subject="maths"), False),
        (_read(subject="code"), False),
        (_read(subject="money"), False),
        (_read(work=True), False),
        (_read(picture="diagram"), False),
        (_read(picture="image"), False),
        (TurnDecision(live=False), False),
    ],
)
def test_only_everyday_chat_by_the_read_is_ordinary(read: TurnDecision, ordinary: bool) -> None:
    assert is_ordinary(read) is ordinary


def _done(read: TurnDecision | None) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    future.set_result(read)
    return future


def _ctx(read: TurnDecision | None) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            {"role": "system", "content": "stable"},
            {"role": "system", "content": "full rules"},
            {"role": "user", "content": "hey whats a good quick dinner idea"},
        ],
        run_title=False,
        user_message_content="hey whats a good quick dinner idea",
        reserved_tokens=100,
        max_output_tokens=100,
    )
    ctx.user = User(id=uuid4(), email="a@b.c", plan="free")
    ctx.auto_routed, ctx.thinking = True, "off"
    ctx.recent_messages = []
    ctx.live_read = _done(read)  # type: ignore[assignment]
    ctx.ordinary_prompt = OrdinaryPrompt(full="full rules", compact="short rules")
    return ctx


@pytest.mark.asyncio
async def test_an_everyday_read_sends_the_short_rules() -> None:
    trace = begin_turn_trace("new")
    ctx = _ctx(_read())
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.prompt_messages[1]["content"] == "short rules"
    assert ctx.prompt_messages[0]["content"] == "stable"
    assert "read.ordinary_prompt" in trace.prompt_rules


@pytest.mark.parametrize(
    "read", [None, _read(subject="physics"), _read(think=True, hard=True), _read(work=True)]
)
@pytest.mark.asyncio
async def test_no_read_or_another_answer_keeps_the_full_rules(read: TurnDecision | None) -> None:
    ctx = _ctx(read)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.prompt_messages[1]["content"] == "full rules"


@pytest.mark.asyncio
async def test_a_regenerate_keeps_the_full_rules() -> None:
    ctx = _ctx(_read())
    ctx.thinking = "escalate"
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.prompt_messages[1]["content"] == "full rules"


def _golden(case_id: str) -> dict[str, Any]:
    return next(case for case in _CASES if case["id"] == case_id)


@pytest.mark.asyncio
async def test_the_switch_off_builds_no_ordinary_rules() -> None:
    case = _golden("branch:steps-career")
    _messages, out = await render(resolve(case, _DEFAULTS))
    assert "ordinary" in out
    off = {**case, "settings": {**case.get("settings", {}), "ordinary_prompt_enabled": False}}
    _messages, out = await render(resolve(off, _DEFAULTS))
    assert "ordinary" not in out


@pytest.mark.parametrize(
    "case_id",
    [
        "branch:brief-profile-fact",
        "battery:personal-capabilities",
        "battery:multi-compare-and-install",
    ],
)
@pytest.mark.asyncio
async def test_a_question_about_the_user_or_several_requests_has_none(case_id: str) -> None:
    _messages, out = await render(resolve(_golden(case_id), _DEFAULTS))
    assert "ordinary" not in out
