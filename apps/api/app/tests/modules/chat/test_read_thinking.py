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

from app.modules.chat.model_routing.thinking import thinking_level, with_read
from app.modules.chat.tool_loop.reply_calls import think_from_the_read
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.turn_reading.lesson_flow import active_lesson_step
from app.modules.web_search.live_read import LiveRead

_LESSON = (
    "## Lesson 1: What a fraction is\n\nA fraction is a part of a whole: 1/2 is one of two "
    "equal parts.\n\nWhich is bigger, 1/2 or 1/3?"
)
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
    think_from_the_read(ctx)
    assert ctx.thinking == after


@pytest.mark.asyncio
async def test_the_reply_never_waits_for_a_read_still_running() -> None:
    ctx = _context(RUNNERS)
    ctx.thinking = "off"
    pending: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    ctx.live_read = pending  # type: ignore[assignment]
    think_from_the_read(ctx)
    assert ctx.thinking == "off"
    ctx.live_read = None
    think_from_the_read(ctx)
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
    think_from_the_read(ctx)
    assert ctx.thinking == after
