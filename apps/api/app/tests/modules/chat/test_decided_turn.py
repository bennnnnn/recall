"""The turn's read decides Auto's lane and the thinking level (``chat.decided_turn``).

A 100-chat check-up on Pro (2026-11-10) sent 76 of 134 turns to the everyday model by word
rules: easy STEM questions the readers missed thought for up to 28 s there, a hard question
almost never reached the strong model. The read's subject and effort now choose, through
catalog data (``ROUTING.decided``); with no read the word rules still do.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.orm import User
from app.models.routing_lanes import ROUTING
from app.modules.chat.decided_turn import decide_from_the_read
from app.modules.chat.model_routing.decided import (
    Effort,
    decided_lane,
    decided_level,
    math_backups,
)
from app.modules.chat.model_routing.thinking import lane_for_think, thinking_level, thinks_when_hard
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.modules.chat.worked_render import WorkedLayout
from app.services.solving import VerifiedSolveBlock
from app.tests.fakes import isolated_settings

_LESSON = (
    "## Lesson 1: What a fraction is\n\nA fraction is a part of a whole: 1/2 is one of two "
    "equal parts.\n\nWhich is bigger, 1/2 or 1/3?"
)
_SETTINGS = isolated_settings()
RUNNERS = (
    "Four runners each ran 100 m in 12 s, 13 s, 14 s and 15 s. Calculate their speeds, chart "
    "them, find the fastest and slowest, and say what you conclude about speed and time."
)
RESISTORS = (
    "Find the equivalent resistance of 10 ohm and 20 ohm in series, then that combination in "
    "parallel with 30 ohm"
)
_POOL = ["free-chat", "smart-chat", "glm-5.3-flash", "glm-5.2", "gpt-6-luna", "qwen-3.7-flash"]
_FREE_POOL = ["qwen-3.7-flash", "free-chat", "glm-5.3-flash"]
_FREE_MATHS = (ROUTING.math_free, "glm-5.3-flash")
_PAID_MATHS = (ROUTING.math, "glm-5.2")


def _read(subject: str | None, think: bool | None, hard: bool = False) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": subject, "think": think, "hard": hard}
    )


def _done(read: TurnDecision | None) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    future.set_result(read)
    return future


def _turn(content: str, read: TurnDecision | None, **fields: Any) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": content}],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )
    ctx.user = User(id=uuid4(), email="a@b.c", plan="pro")
    ctx.auto_routed, ctx.thinking = True, "off"
    ctx.fallback_models = ["smart-chat", "qwen-3.7-flash"]
    ctx.live_read = _done(read)  # type: ignore[assignment]
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


@pytest.mark.parametrize(
    ("subject", "effort", "level"),
    [
        ("everyday", "none", "off"),
        ("everyday", "low", "hard"),
        ("everyday", "high", "deep"),
        ("code", "low", "hard"),
        # STEM thinks only when hard: C17 and C14 waited 11.7 s and 15.5 s at "low".
        ("maths", "low", "off"),
        ("physics", "low", "off"),
        ("chemistry", "low", "off"),
        ("maths", "high", "hard"),
        ("physics", "none", "off"),
    ],
)
def test_the_level_comes_from_the_subject_and_effort(subject: str, effort: Any, level: str) -> None:
    assert decided_level(subject, effort) == level


@pytest.mark.parametrize(
    ("subject", "effort", "lane"),
    [
        # Pro's everyday model answers everyday turns, thinking or not.
        ("everyday", "none", "free-chat"),
        ("everyday", "low", "free-chat"),
        # A hard everyday question goes to the strong lane (the owner's call, 2026-11-10).
        ("everyday", "high", "smart-chat"),
        ("code", "none", "free-chat"),
        # A low code question (E17, a git how-to) stays on the everyday lane, thinking there.
        ("code", "low", "free-chat"),
        ("code", "high", "smart-chat"),
        # STEM nothing verified: the maths lane, whatever subject the readers missed, hard
        # or not (the owner's call, 2026-11-11).
        ("maths", "none", ROUTING.math),
        ("physics", "low", ROUTING.math),
        ("chemistry", "high", ROUTING.math),
        # Money keeps the word rules' lane: its calculator card holds the numbers.
        ("money", "low", None),
    ],
)
def test_the_lane_comes_from_the_catalogs_table(subject: str, effort: Any, lane: str) -> None:
    assert decided_lane(subject, effort, _POOL, strong_everyday=True) == lane


def test_a_plan_without_the_strong_models_gets_its_pools_best() -> None:
    """Free's pool has no smart model: its STEM questions go to its own maths lane (Qwen3.7
    Flash, the owner's call, 2026-11-11), hard ones too; its hard everyday questions to GLM
    5.3 Flash, its everyday ones to its everyday model."""
    stem: list[tuple[str, Effort]] = [("maths", "low"), ("physics", "none"), ("chemistry", "high")]
    for subject, effort in stem:
        assert decided_lane(subject, effort, _FREE_POOL, math_lane=_FREE_MATHS) == ROUTING.math_free
    assert decided_lane("everyday", "high", _FREE_POOL) == "glm-5.3-flash"
    assert decided_lane("everyday", "none", _FREE_POOL) == ROUTING.everyday


@pytest.mark.parametrize(("pool", "chain"), [(_POOL, _PAID_MATHS), (_FREE_POOL, _FREE_MATHS)])
def test_a_stem_lane_falls_back_to_glm(pool: list[str], chain: tuple[str, str]) -> None:
    """DeepSeek on a paid plan and Qwen on Free each fall back to GLM first; while the lane's
    breaker is open, or the user switched it off, the turn starts on GLM."""
    lane, backup = chain
    assert decided_lane("physics", "none", pool, math_lane=chain) == lane
    assert math_backups("physics", lane, pool) == [backup]
    unsteady = frozenset({lane})
    assert decided_lane("maths", "high", pool, unsteady=unsteady, math_lane=chain) == backup
    switched_off = [alias for alias in pool if alias != lane]
    assert decided_lane("chemistry", "low", switched_off, math_lane=chain) == backup
    assert math_backups("maths", lane, pool, frozenset({backup})) == []
    # Only STEM: a hard everyday question on DeepSeek keeps the pool's order.
    assert math_backups("everyday", lane, pool) == []


def test_a_paid_plan_never_gets_frees_maths_lane() -> None:
    """With DeepSeek and GLM 5.2 both switched off, a paid STEM turn goes to the strongest
    model left, not to Free's Qwen lane."""
    pool = [alias for alias in _POOL if alias not in _PAID_MATHS]
    assert decided_lane("maths", "none", pool, math_lane=_PAID_MATHS) == "glm-5.3-flash"


@pytest.mark.asyncio
async def test_a_stem_turn_tries_glm_before_the_rules_model() -> None:
    ctx = _turn(RESISTORS, _read("physics", False))
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.model == ROUTING.math
    assert ctx.fallback_models == ["glm-5.2", "free-chat", "qwen-3.7-flash"]


def test_a_lane_never_goes_to_a_model_whose_breaker_is_open() -> None:
    lane = decided_lane("everyday", "high", _POOL, unsteady=frozenset({"smart-chat"}))
    assert lane is not None and lane != "smart-chat"


def test_with_no_read_the_word_rules_decide() -> None:
    # The word rules give this word problem no thinking: the case the read fixes.
    assert thinking_level(RUNNERS) == "off"
    assert thinking_level("```python\nprint(1)\n```\nwhy does this fail?") == "hard"


def test_the_maths_lane_is_no_reason_to_think() -> None:
    """With the maths lane on the strong model, the word rules still give an equation no
    thinking: the solver checks it."""
    assert thinking_level("solve 2x + 5 = 17") == "off"
    assert thinking_level("integrate x e^x dx") == "off"


@pytest.mark.asyncio
async def test_a_hard_everyday_question_moves_to_the_strong_lane_and_thinks_deep() -> None:
    begin_turn_trace("new")
    ctx = _turn("Should we hire two juniors or one senior?", _read("everyday", True, True))
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("smart-chat", "deep")
    # The lane it left is the first backup.
    assert ctx.fallback_models == ["free-chat", "qwen-3.7-flash"]


@pytest.mark.asyncio
async def test_an_easy_question_answers_at_once() -> None:
    """E21, a packing list: the check-up thought 4.5 s on it."""
    ctx = _turn("What should I pack for Iceland?", _read("everyday", False), thinking="hard")
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("free-chat", "off")


@pytest.mark.asyncio
async def test_stem_the_readers_missed_gets_its_lane_and_the_worked_layout() -> None:
    """P16: no reader claimed it, so it went to the everyday model with heavy thinking and
    the everyday prompt (28 s to the first word)."""
    ctx = _turn(RESISTORS, _read("physics", True), thinking="hard")
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == (ROUTING.math, "off")
    assert ctx.worked is not None
    assert any("```worked" in str(m.get("content")) for m in ctx.prompt_messages)


@pytest.mark.parametrize(
    "fields",
    [
        {"verified_subject": VerifiedSolveBlock(text="x = 6", subject="math")},
        {"money": MagicMock(name="money")},
    ],
    ids=["verified", "money"],
)
@pytest.mark.asyncio
async def test_numbers_the_server_worked_keep_their_lane_and_level(fields: dict[str, Any]) -> None:
    ctx = _turn("solve 2x + 5 = 17", _read("maths", True), **fields)
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking, ctx.worked) == ("free-chat", "off", None)


@pytest.mark.asyncio
async def test_a_model_the_user_picked_keeps_it_and_takes_the_level() -> None:
    ctx = _turn("Should we hire two juniors?", _read("everyday", True, True), auto_routed=False)
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("free-chat", "deep")


@pytest.mark.parametrize("before", ["off", "escalate"])
@pytest.mark.asyncio
async def test_a_lesson_keeps_its_quick_steps(before: str) -> None:
    ctx = _turn(
        "next",
        _read("maths", True),
        thinking=before,
        recent_messages=[
            SimpleNamespace(role="assistant", content=_LESSON),
            SimpleNamespace(role="user", content="next"),
        ],
    )
    await decide_from_the_read(ctx, _SETTINGS)
    # The lesson's quick lane and level stay, as the word rules keep them (``route``).
    assert (ctx.model, ctx.thinking) == ("free-chat", before)


@pytest.mark.asyncio
async def test_a_regenerate_or_a_dispute_keeps_its_escalation_and_lane() -> None:
    ctx = _turn("that's wrong", _read("everyday", False), thinking="escalate")
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("free-chat", "escalate")


@pytest.mark.parametrize("read", [None, _read("everyday", None)], ids=["no read", "no effort"])
@pytest.mark.asyncio
async def test_with_no_answer_the_word_rules_stand(read: TurnDecision | None) -> None:
    trace = begin_turn_trace("new")
    ctx = _turn("Should we hire two juniors?", read, thinking="hard")
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("free-chat", "hard")
    assert trace.decision == {"decided_by": "rules"}


@pytest.mark.asyncio
async def test_the_trace_says_the_read_decided() -> None:
    trace = begin_turn_trace("new")
    ctx = _turn("Draw it", _read("chemistry", False))
    await decide_from_the_read(ctx, _SETTINGS)
    assert trace.decision is not None and trace.decision["decided_by"] == "read"
    assert (trace.decision["subject"], trace.decision["effort"]) == ("chemistry", "none")


@pytest.mark.asyncio
async def test_a_read_still_running_is_waited_for_only_when_it_could_move_the_lane() -> None:
    pending: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    ctx = _turn("hi", None, auto_routed=False)
    ctx.live_read = pending  # type: ignore[assignment]
    await decide_from_the_read(ctx, isolated_settings(live_read_wait_seconds=5))
    assert not pending.cancelled()
    # Auto's lane could move: the turn waits as long as a search would, then the rules stand.
    ctx = _turn("hi", None)
    ctx.live_read = pending  # type: ignore[assignment]
    await decide_from_the_read(ctx, isolated_settings(live_read_wait_seconds=0.01))
    assert pending.cancelled() and ctx.model == "free-chat"


@pytest.mark.asyncio
async def test_a_photo_turn_keeps_the_model_that_reads_it() -> None:
    photo = [{"type": "text", "text": "what is this?"}, {"type": "image_url", "image_url": {}}]
    ctx = _turn("what is this?", _read("everyday", True, True), model="vision-chat")
    ctx.prompt_messages = [{"role": "user", "content": photo}]
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.model == "vision-chat"


@pytest.mark.asyncio
async def test_a_worked_layout_already_set_is_left_alone() -> None:
    layout = WorkedLayout(law_heading=False)
    ctx = _turn(RESISTORS, _read("physics", False), worked=layout)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is layout
    assert not any("```worked" in str(m.get("content")) for m in ctx.prompt_messages)


def test_the_maths_lane_moves_to_a_model_that_can_think() -> None:
    assert not thinks_when_hard("glm-5.2") and thinks_when_hard("smart-chat")
    with_glm = [m for m in _POOL if m != ROUTING.math] + ["glm-5.2"]
    assert lane_for_think("qwen-3.7-flash", with_glm) is None
    assert lane_for_think("smart-chat", _POOL) is None


@pytest.mark.parametrize(
    "content", ["Name this compound: CH3CH2CH2OH", "Give me a practice question for grade 11"]
)
@pytest.mark.asyncio
async def test_a_digit_that_is_no_value_gets_no_worked_layout(content: str) -> None:
    """Live (2026-11-10): "Name this compound: CH3CH2CH2OH" got a Given and a Required."""
    ctx = _turn(content, _read("chemistry", False))
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is None


@pytest.mark.asyncio
async def test_a_hard_stem_problem_still_thinks() -> None:
    """The four runners' speeds (2026-11-09): the read calls it hard, and it thinks."""
    ctx = _turn(RUNNERS, _read("physics", True, True))
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == (ROUTING.math, "hard")


@pytest.mark.asyncio
async def test_a_low_everyday_question_thinks_on_the_everyday_model() -> None:
    ctx = _turn("How do I fix git push rejected non-fast-forward?", _read("code", True))
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.model, ctx.thinking) == ("free-chat", "hard")


@pytest.mark.parametrize(
    "fields",
    [
        {"lightweight_turn": True},
        {"user_message_content": "give me the list of the planets as valid JSON"},
        {"recent_messages": [SimpleNamespace(role="assistant", content=_LESSON)]},
    ],
    ids=["small talk", "json ask", "lesson"],
)
@pytest.mark.asyncio
async def test_a_turn_whose_lane_cannot_move_never_waits_for_the_read(
    fields: dict[str, Any],
) -> None:
    """ "thanks!" waited the whole 1.2 s for a read that could change nothing (review,
    2026-11-10). The wait and the move ask one test (``_lane_may_move``)."""
    pending: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    ctx = _turn("thanks!", None, **fields)
    ctx.live_read = pending  # type: ignore[assignment]
    await asyncio.wait_for(
        decide_from_the_read(ctx, isolated_settings(live_read_wait_seconds=5)), 0.5
    )
    assert not pending.done() and ctx.model == "free-chat"
    pending.cancel()


@pytest.mark.asyncio
async def test_a_photo_turn_never_waits_for_the_read() -> None:
    photo = [{"type": "text", "text": "what is this?"}, {"type": "image_url", "image_url": {}}]
    pending: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    ctx = _turn("what is this?", None, model="vision-chat")
    ctx.prompt_messages = [{"role": "user", "content": photo}]
    ctx.live_read = pending  # type: ignore[assignment]
    await asyncio.wait_for(
        decide_from_the_read(ctx, isolated_settings(live_read_wait_seconds=5)), 0.5
    )
    assert not pending.done()
    pending.cancel()
