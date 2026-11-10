"""The turn's read says whether to think first (``live_read``'s ``think``).

A four-part word problem about four runners' speeds (2026-11-09) got no thinking from the
word rules and a weak answer; its regenerate, thinking, answered well. The read decides
when it answers by the reply's call; with no answer, the word rules still do. A regenerate
or a disputed answer escalates as before.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.model_routing.thinking import (
    lane_for_think,
    thinking_level,
    thinks_when_hard,
    with_read,
)
from app.modules.chat.tool_loop.reply_calls import think_from_the_read
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.turn_reading.lesson_flow import active_lesson_step
from app.modules.web_search.live_read import LiveRead
from app.services.solving import VerifiedSolveBlock

_LESSON = (
    "## Lesson 1: What a fraction is\n\nA fraction is a part of a whole: 1/2 is one of two "
    "equal parts.\n\nWhich is bigger, 1/2 or 1/3?"
)
_SETTINGS = Settings(_env_file=None)  # type: ignore[call-arg]
RUNNERS = (
    "Four runners each ran 100 m in 12 s, 13 s, 14 s and 15 s. Calculate their speeds, chart "
    "them, find the fastest and slowest, and say what you conclude about speed and time."
)


@pytest.mark.parametrize(("think", "level"), [(True, "hard"), (False, "off")])
def test_the_reads_answer_sets_the_level(think: bool, level: str) -> None:
    assert thinking_level(RUNNERS, read_think=think) == level


def test_with_no_read_the_word_rules_decide() -> None:
    # The word rules give this word problem no thinking: the case the read fixes.
    assert thinking_level(RUNNERS) == "off"
    assert thinking_level("```python\nprint(1)\n```\nwhy does this fail?") == "hard"


@pytest.mark.parametrize("think", [True, False])
def test_a_regenerate_or_a_dispute_still_escalates(think: bool) -> None:
    assert thinking_level(RUNNERS, regenerate=True, read_think=think) == "escalate"
    assert thinking_level("that's wrong", prior_user=RUNNERS, read_think=think) == "escalate"
    assert with_read(think, "escalate") == "escalate"


def _context(content: str) -> StreamContext:
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="gpt-6-luna",
        prompt_messages=[{"role": "user", "content": content}],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )


def _done(read: LiveRead | None) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    future.set_result(read)
    return future


@pytest.mark.parametrize(
    ("read", "before", "after"),
    [
        (LiveRead(live=False, think=True), "off", "hard"),
        (LiveRead(live=False, think=False), "hard", "off"),
        (LiveRead(live=False, think=False), "escalate", "escalate"),
        # The read gave no answer: the word rules' level stands.
        (None, "hard", "hard"),
    ],
)
@pytest.mark.asyncio
async def test_the_reply_takes_the_reads_level_when_it_is_in(
    read: LiveRead | None, before: str, after: str
) -> None:
    ctx = _context(RUNNERS)
    ctx.thinking = before
    ctx.live_read = _done(read)  # type: ignore[assignment]
    think_from_the_read(ctx, _SETTINGS)
    assert ctx.thinking == after


@pytest.mark.asyncio
async def test_the_reply_never_waits_for_a_read_still_running() -> None:
    ctx = _context(RUNNERS)
    ctx.thinking = "off"
    pending: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    ctx.live_read = pending  # type: ignore[assignment]
    think_from_the_read(ctx, _SETTINGS)
    assert ctx.thinking == "off"
    ctx.live_read = None
    think_from_the_read(ctx, _SETTINGS)
    assert ctx.thinking == "off"
    pending.cancel()


def test_a_lesson_step_never_thinks_on_the_reads_word() -> None:
    """A lesson's next step or practice problem stays on the fast lesson lane, thinking off,
    as the word rules keep it; a regenerate or a dispute still escalates."""
    assert thinking_level("next", lesson_active=True, read_think=True) == "off"
    assert thinking_level(RUNNERS, lesson_active=True, read_think=True) == "off"
    assert thinking_level("next", lesson_active=True, regenerate=True, read_think=True) == (
        "escalate"
    )
    assert with_read(True, "off", lesson_active=True) == "off"
    assert with_read(True, "escalate", lesson_active=True) == "escalate"


@pytest.mark.parametrize(("before", "after"), [("off", "off"), ("escalate", "escalate")])
@pytest.mark.asyncio
async def test_the_reply_keeps_a_lessons_level_whatever_the_read_says(
    before: str, after: str
) -> None:
    ctx = _context("next")
    ctx.recent_messages = [
        SimpleNamespace(role="user", content="teach me fractions"),
        SimpleNamespace(role="assistant", content=_LESSON),
        SimpleNamespace(role="user", content="next"),
    ]
    assert active_lesson_step(ctx.recent_messages) == 1
    ctx.thinking = before
    ctx.live_read = _done(LiveRead(live=False, think=True))  # type: ignore[assignment]
    think_from_the_read(ctx, _SETTINGS)
    assert ctx.thinking == after


_POOL = ["free-chat", "smart-chat", "glm-5.3-flash", "glm-5.2", "gpt-6-luna", "qwen-3.7-flash"]


def test_the_maths_lane_moves_to_a_model_that_can_think() -> None:
    assert not thinks_when_hard("glm-5.2") and thinks_when_hard("smart-chat")
    assert lane_for_think("glm-5.2", _POOL) == "smart-chat"
    # With the smart lane switched off, no strong model left thinks: the lane stays.
    assert lane_for_think("glm-5.2", [m for m in _POOL if m != "smart-chat"]) is None
    # The everyday lane, a model that thinks, and a pool with no strong model stay.
    assert lane_for_think("qwen-3.7-flash", _POOL) is None
    assert lane_for_think("smart-chat", _POOL) is None
    assert lane_for_think("glm-5.2", ["glm-5.2", "qwen-3.7-flash"]) is None


def _maths_turn(**fields: Any) -> Any:
    ctx = _context(RUNNERS)
    ctx.model, ctx.fallback_models = "glm-5.2", ["smart-chat", "free-chat"]
    ctx.user = User(id=uuid4(), email="a@b.c", plan="pro")
    ctx.auto_routed, ctx.thinking = True, "off"
    ctx.live_read = _done(LiveRead(live=False, think=True))  # type: ignore[assignment]
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


@pytest.mark.asyncio
async def test_an_auto_word_problem_the_read_says_to_think_on_moves_lane() -> None:
    ctx = _maths_turn()
    think_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("smart-chat", "hard")
    # The lane it left is the first backup.
    assert ctx.fallback_models == ["glm-5.2", "free-chat"]


@pytest.mark.parametrize(
    "fields",
    [
        {"auto_routed": False},
        {"verified_subject": VerifiedSolveBlock(text="x = 6", subject="math")},
        {"live_read": None},
    ],
    ids=["own pick", "verified", "no read"],
)
@pytest.mark.asyncio
async def test_the_maths_lane_stays_for_a_pick_a_verified_solve_or_no_read(
    fields: dict[str, Any],
) -> None:
    ctx = _maths_turn(**fields)
    think_from_the_read(ctx, _SETTINGS)
    assert ctx.model == "glm-5.2"


@pytest.mark.asyncio
async def test_a_lesson_keeps_its_lane() -> None:
    ctx = _maths_turn(
        recent_messages=[
            SimpleNamespace(role="assistant", content=_LESSON),
            SimpleNamespace(role="user", content="next"),
        ]
    )
    think_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("glm-5.2", "off")


@pytest.mark.parametrize("unsteady", [{"smart-chat"}, {"smart-chat", "gpt-6-luna"}])
def test_the_move_never_goes_to_a_model_whose_breaker_is_open(unsteady: set[str]) -> None:
    """With DeepSeek's breaker open the turn would wait out its timeout there first."""
    assert lane_for_think("glm-5.2", _POOL, frozenset(unsteady)) is None


@pytest.mark.asyncio
async def test_an_unsteady_smart_lane_keeps_the_maths_lane() -> None:
    ctx = _maths_turn(unsteady_models=frozenset({"smart-chat"}))
    think_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("glm-5.2", "hard")
