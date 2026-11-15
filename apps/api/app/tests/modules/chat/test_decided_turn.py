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
from app.modules.chat.lesson_layout import prompt_lesson_layout
from app.modules.chat.model_routing.decided import (
    Effort,
    decided_lane,
    decided_level,
    math_backups,
)
from app.modules.chat.model_routing.thinking import thinking_level
from app.modules.chat.prompt_constants.conversation import FOLLOW_NOTES
from app.modules.chat.prompt_constants.lesson_flow import LESSON_ASIDE_NOTE, lesson_next_contract
from app.modules.chat.prompt_constants.practice import QUIZ_WHICH_NOTE
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_turn import with_worked_contract
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
_POOL = [
    "free-chat",
    "smart-chat",
    "glm-5.3-flash",
    "qwen-3.8-flash",
    "gpt-6-luna",
    "qwen-3.7-flash",
]
_FREE_POOL = ["qwen-3.7-flash", "free-chat", "glm-5.3-flash"]
_FREE_MATHS = (ROUTING.math_free, "glm-5.3-flash")
_PAID_MATHS = (ROUTING.math, "qwen-3.8-flash")


def _read(
    subject: str | None, think: bool | None, hard: bool = False, work: bool | None = None
) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": subject, "think": think, "hard": hard, "work": work}
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
def test_a_stem_lane_falls_back_to_its_backup(pool: list[str], chain: tuple[str, str]) -> None:
    """DeepSeek on a paid plan falls back to Qwen3.8 Flash, Qwen3.7 Flash on Free to GLM 5.3
    Flash; while the lane's breaker is open, or the user switched it off, the turn starts on
    the backup."""
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
    """With DeepSeek and Qwen3.8 Flash both switched off, a paid STEM turn goes to the strongest
    model left, not to Free's Qwen lane."""
    pool = [alias for alias in _POOL if alias not in _PAID_MATHS]
    assert decided_lane("maths", "none", pool, math_lane=_PAID_MATHS) == "glm-5.3-flash"


@pytest.mark.asyncio
async def test_a_stem_turn_tries_its_backup_before_the_rules_model() -> None:
    ctx = _turn(RESISTORS, _read("physics", False))
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.model == ROUTING.math
    assert ctx.fallback_models == ["qwen-3.8-flash", "free-chat", "qwen-3.7-flash"]


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
    ],
    ids=["small talk", "json ask"],
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


@pytest.mark.parametrize("late", [False, True], ids=["in time", "late"])
@pytest.mark.asyncio
async def test_a_turn_after_a_card_waits_for_the_read(late: bool) -> None:
    """ "b" went ungraded whenever the read came in after the prep: a lesson's turn never
    waited for it (review, 2026-11-14). It waits as long as the reply waits for any read;
    later than that, the system prompt's lesson steps stand."""
    loop = asyncio.get_event_loop()
    pending: asyncio.Future[Any] = loop.create_future()
    recent = [
        SimpleNamespace(role="user", content="teach me atoms"),
        SimpleNamespace(role="assistant", content=_LESSON_ONE),
    ]
    ctx = _turn("b", None, recent_messages=recent)
    ctx.live_read = pending  # type: ignore[assignment]
    read = _card_read(["b"], goes_on=True)

    def answer() -> None:
        if not pending.done():  # The reply stopped waiting, and cancelled it.
            pending.set_result(read)

    loop.call_later(0.3 if late else 0.05, answer)
    trace = begin_turn_trace("new")
    await decide_from_the_read(ctx, isolated_settings(live_read_wait_seconds=0.2))
    assert ("read.quiz_answer" in trace.prompt_rules) is not late
    if late:
        assert ctx.prompt_messages == [{"role": "user", "content": "b"}]
    else:
        assert "Exercise 1: the answer given, 35, is right." in _note(ctx)


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


_PYTHON_ASK = "Do you mean Python the programming language, or the snake? 🐍"
_OUTLINE = (
    "Here's how we could learn Python:\n\n1. Variables\n2. Loops\n3. Functions\n\n"
    "Where would you like to start?"
)


def _follow_read(follow: str, subject: str = "everyday") -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": subject, "think": False, "follow": follow}
    )


def _follow_turn(content: str, read: TurnDecision, **fields: Any) -> StreamContext:
    ctx = _turn(content, read, **fields)
    ctx.prompt_messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "is python hard?"},
        {"role": "assistant", "content": _PYTHON_ASK},
        {"role": "user", "content": content},
    ]
    return ctx


@pytest.mark.parametrize(
    ("follow", "subject", "note"),
    [
        # Pro phone test (2026-11-11): Claude Haiku asked "the language" back on every try,
        # and "Top 5 in Ethiopia" after the world's top universities.
        ("answer", "everyday", FOLLOW_NOTES["answer"]),
        ("change", "everyday", FOLLOW_NOTES["change"]),
        ("answer", "code", FOLLOW_NOTES["answer"]),
        # A new question, or more on the last answer: nothing to say.
        ("none", "everyday", None),
        ("explain", "everyday", None),
        # Maths, physics, chemistry and money read their own follow-ups.
        ("change", "maths", None),
        ("answer", "physics", None),
        ("change", "money", None),
    ],
)
@pytest.mark.asyncio
async def test_the_read_says_how_the_message_leans_on_the_conversation(
    follow: str, subject: str, note: str | None
) -> None:
    trace = begin_turn_trace("new")
    ctx = _follow_turn("the language", _follow_read(follow, subject))
    await decide_from_the_read(ctx, _SETTINGS)
    notes = [m["content"] for m in ctx.prompt_messages if m["content"] in FOLLOW_NOTES.values()]
    assert notes == ([note] if note else [])
    if note:
        # Beside the message, after the history: a small model follows the nearest note.
        assert ctx.prompt_messages[-2:] == [
            {"role": "system", "content": note},
            {"role": "user", "content": "the language"},
        ]
        assert f"read.follow_{follow}" in trace.prompt_rules
    else:
        assert not any(rule.startswith("read.follow") for rule in trace.prompt_rules)


@pytest.mark.parametrize(
    "fields",
    [
        {"after_card": True},
        {"recent_messages": [SimpleNamespace(role="assistant", content=_LESSON)]},
        # Numbers a server path worked are the reply's to present (review, 2026-11-11).
        {"verified_subject": VerifiedSolveBlock(text="x = 6", subject="math")},
        {"money": MagicMock(name="money")},
        {
            "recent_messages": [
                SimpleNamespace(role="user", content="teach me python"),
                SimpleNamespace(role="assistant", content=_OUTLINE),
            ]
        },
        # A calculation the subject readers gave the ```worked contract: the block lays it
        # out, whatever the read calls the subject (review, 2026-11-11).
        {"worked": WorkedLayout()},
    ],
    ids=["clarify card", "lesson", "verified", "money", "outline", "worked"],
)
@pytest.mark.asyncio
async def test_a_turn_that_reads_its_reply_its_own_way_gets_no_follow_note(
    fields: dict[str, Any],
) -> None:
    """A card's picks, a lesson's answer and an outline's pick have their own notes, and a
    server path's numbers their own reply."""
    ctx = _follow_turn("variables", _follow_read("answer"), **fields)
    await decide_from_the_read(ctx, _SETTINGS)
    assert not any(m["content"] in FOLLOW_NOTES.values() for m in ctx.prompt_messages)


_SEVEN_X = "Translate the algebraic expression 7x in different word phrases."


@pytest.mark.asyncio
async def test_a_message_that_works_nothing_out_loses_the_readers_layout() -> None:
    """Phone, 2026-11-13: its 7 gave it the ```worked contract, and the reply came under a
    Given and a Required, "phrases" set as a symbol. The read says it works nothing out."""
    trace = begin_turn_trace("new")
    ctx = _turn(_SEVEN_X, _read("maths", False, work=False), worked=WorkedLayout())
    ctx.prompt_messages = with_worked_contract(ctx.prompt_messages)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is None
    assert not any("```worked" in str(m.get("content")) for m in ctx.prompt_messages)
    assert "read.not_worked" in trace.prompt_rules
    assert trace.decision is not None and trace.decision["work"] == "no"


@pytest.mark.asyncio
async def test_a_calculation_the_read_calls_work_keeps_the_readers_layout() -> None:
    layout = WorkedLayout()
    ctx = _turn("Solve 3x + 7 = 22.", _read("maths", False, work=True), worked=layout)
    ctx.prompt_messages = with_worked_contract(ctx.prompt_messages)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is layout
    assert any("```worked" in str(m.get("content")) for m in ctx.prompt_messages)


@pytest.mark.parametrize(("work", "laid_out"), [(True, True), (False, False), (None, True)])
@pytest.mark.asyncio
async def test_stem_the_readers_missed_is_laid_out_as_the_read_says(
    work: bool | None, laid_out: bool
) -> None:
    """With no word on the work (the text read's), the rules' value test decides."""
    ctx = _turn(RESISTORS, _read("physics", False, work=work))
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.worked is not None) is laid_out


@pytest.mark.asyncio
async def test_a_question_a_subject_declined_keeps_the_layout_its_readers_gave() -> None:
    """Its readers read it: one with no answer as written ("a -5 Ω resistor") was given no
    ```worked block, whose contract would have the model work the value out (live round,
    2026-11-14), and the read does not add one."""
    ctx = _turn(
        "A 10 V battery is connected across a -5 Ω resistor. What current flows?",
        _read("physics", False, work=True),
        solver_unverified=True,
        unverified_subject="physics",
    )
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is None
    assert not any("```worked" in str(m.get("content")) for m in ctx.prompt_messages)


@pytest.mark.asyncio
async def test_a_regenerate_waits_for_the_read_when_its_layout_is_at_stake() -> None:
    """Its lane and escalation stay, but the 7x question regenerated must not come back under
    a Given and a Required because the read was still on its way."""
    loop = asyncio.get_event_loop()
    pending: asyncio.Future[Any] = loop.create_future()
    ctx = _turn(_SEVEN_X, None, thinking="escalate", worked=WorkedLayout())
    ctx.prompt_messages = with_worked_contract(ctx.prompt_messages)
    ctx.live_read = pending  # type: ignore[assignment]
    loop.call_later(0.01, pending.set_result, _read("maths", False, work=False))
    await decide_from_the_read(ctx, isolated_settings(live_read_wait_seconds=1))
    assert (ctx.worked, ctx.thinking, ctx.model) == (None, "escalate", "free-chat")


@pytest.mark.parametrize("content", ["2", "42"])
@pytest.mark.asyncio
async def test_the_reads_work_never_adds_a_layout_the_rules_would_not(content: str) -> None:
    """A lesson's pick or a quiz answer stays plain, whatever the read says of it."""
    ctx = _turn(content, _read("maths", False, work=True))
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is None


# The owner's chat (2026-11-14): Lesson 2 ended on this card, and "1.2 times 10 to the 24?"
# came back laid out Given to Answer, then "you're asking how that compares to the card?".
_MOLES_LESSON = (
    "### Lesson 2: Moles and particles\n\n### 1. Counting particles\n\n$$N = n \\times N_A$$\n\n"
    "### Your turn\n\n```quiz\n"
    '{"label": "Exercise 2", "question": "How many molecules are in 2 mol of water?", '
    '"options": ["6.02 × 10²³", "1.204 × 10²⁴", "2 × 10²³"], "answer": 1, '
    '"explanation": "2 × 6.02 × 10²³."}\n```'
)
_AFTER_CARD = [
    SimpleNamespace(role="user", content="2 mol. continue"),
    SimpleNamespace(role="assistant", content=_MOLES_LESSON),
]


def _card_read(
    picks: list[str] | None,
    *,
    goes_on: bool | None = None,
    follow: str = "answer",
    answers: bool | None = None,
    unplaced: bool | None = None,
) -> TurnDecision:
    """The read after cards; ``answers`` defaults to whether a pick names an option."""
    if answers is None and picks is not None:
        answers = any(pick != "none" for pick in picks)
    return TurnDecision.model_validate(
        {
            "live": False,
            "subject": "chemistry",
            "think": False,
            "follow": follow,
            "work": True,
            "card_picks": picks,
            "answers": answers,
            "unplaced": unplaced,
            "goes_on": goes_on,
        }
    )


def _note(ctx: StreamContext) -> str:
    return str(ctx.prompt_messages[-2]["content"])


@pytest.mark.parametrize(
    ("content", "pick", "verdict"),
    [
        # "b", "the second one", "is it 1.204 x 10^24", "B": the read names option B. The
        # verdict names it by its words, as the phone's card shows it, never its letter.
        ("b", "b", "Exercise 2: the answer given, 1.204 × 10²⁴, is right."),
        ("the second one", "b", "Exercise 2: the answer given, 1.204 × 10²⁴, is right."),
        (
            "a",
            "a",
            "Exercise 2: the answer given, 6.02 × 10²³, is wrong; the right answer is 1.204 × 10²⁴.",
        ),
        (
            "is it 2 × 10^23",
            "c",
            "Exercise 2: the answer given, 2 × 10²³, is wrong; the right answer is 1.204",
        ),
        # A value none of the options is: the reply judges whether it means the right one.
        (
            "1.2 times 10 to the 24?",
            "other",
            "Exercise 2: the answer given is none of the options; the right answer is 1.204 × 10²⁴.",
        ),
    ],
)
@pytest.mark.parametrize("readers_layout", [False, True], ids=["read's layout", "readers' layout"])
@pytest.mark.asyncio
async def test_an_answer_to_the_card_is_graded_by_the_server(
    content: str, pick: str, verdict: str, readers_layout: bool
) -> None:
    """Told only the right answer's words, the reply graded "b" for B wrong and "a" right, and
    read "the second one" as the third option (review, 2026-11-14)."""
    trace = begin_turn_trace("new")
    fields: dict[str, Any] = {"recent_messages": _AFTER_CARD}
    if readers_layout:
        fields["worked"] = WorkedLayout()
    ctx = _turn(content, _card_read([pick]), **fields)
    if readers_layout:
        ctx.prompt_messages = with_worked_contract(ctx.prompt_messages)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is None
    assert not any("```worked" in str(m.get("content")) for m in ctx.prompt_messages)
    assert verdict in _note(ctx)
    assert "they chose" not in _note(ctx) and "(B)" not in _note(ctx)
    assert ctx.prompt_messages[-1] == {"role": "user", "content": content}
    assert "read.quiz_answer" in trace.prompt_rules
    # Lesson 2's card answered: Lesson 3 comes next.
    assert any(m["content"] == lesson_next_contract(2) for m in ctx.prompt_messages)


@pytest.mark.parametrize(
    ("picks", "follow"),
    [
        # A new question after the card answers none of it, and is worked as any question is.
        (["none"], "solve"),
        (["none"], "none"),
        # No read of the cards (late, or the text read): the rules stand.
        (None, "answer"),
    ],
    ids=["new question", "no option named", "cards unread"],
)
@pytest.mark.asyncio
async def test_a_message_that_answers_no_card_keeps_its_worked_layout(
    picks: list[str] | None, follow: str
) -> None:
    trace = begin_turn_trace("new")
    content = "How many molecules are in 3 mol of carbon dioxide?"
    ctx = _turn(content, _card_read(picks, follow=follow), recent_messages=_AFTER_CARD)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.worked is not None
    assert "read.quiz_answer" not in trace.prompt_rules


@pytest.mark.asyncio
async def test_each_card_of_a_set_gets_its_own_verdict() -> None:
    cards = "\n\n".join(
        "```quiz\n"
        f'{{"label": "Mixed {n}", "question": "Q{n}?", "options": ["x", "y", "z"], "answer": {n % 3}}}'
        "\n```"
        for n in range(1, 4)
    )
    recent = [SimpleNamespace(role="assistant", content=f"A mixed set.\n\n{cards}")]
    ctx = _turn("y, z, x", _card_read(["b", "none", "a"], unplaced=False), recent_messages=recent)
    await decide_from_the_read(ctx, _SETTINGS)
    note = _note(ctx)
    assert "Mixed 1: the answer given, y, is right." in note
    assert "Mixed 3: the answer given, x, is right." in note
    assert "Mixed 2" not in note


def _mixed_set(options: str = '["x", "y", "z"]') -> list[Any]:
    cards = "\n\n".join(
        "```quiz\n"
        f'{{"label": "Mixed {n}", "question": "Q{n}?", "options": {options}, "answer": {n % 3}}}'
        "\n```"
        for n in range(1, 4)
    )
    return [SimpleNamespace(role="assistant", content=f"A mixed set.\n\n{cards}")]


@pytest.mark.asyncio
async def test_one_answer_that_could_be_any_cards_is_asked_about_first() -> None:
    """A lone "B" after three cards was graded against each of them (review, 2026-11-14):
    the reply asks which question it answers, grades nothing and starts nothing."""
    trace = begin_turn_trace("new")
    read = _card_read(["b", "b", "b"], unplaced=True)
    ctx = _turn("B", read, recent_messages=_mixed_set())
    await decide_from_the_read(ctx, _SETTINGS)
    assert _note(ctx) == QUIZ_WHICH_NOTE
    assert "read.quiz_which" in trace.prompt_rules
    assert "read.quiz_answer" not in trace.prompt_rules


@pytest.mark.asyncio
async def test_one_answer_the_read_places_on_one_card_is_graded() -> None:
    """ "Q2: B" names its card; and one answer only one card takes is that card's."""
    for picks, unplaced in ((["none", "b", "none"], False), (["none", "b", "none"], True)):
        trace = begin_turn_trace("new")
        ctx = _turn("Q2: B", _card_read(picks, unplaced=unplaced), recent_messages=_mixed_set())
        await decide_from_the_read(ctx, _SETTINGS)
        assert "Mixed 2: the answer given, y, is wrong; the right answer is z." in _note(ctx)
        assert "read.quiz_which" not in trace.prompt_rules


@pytest.mark.parametrize(
    ("content", "pick", "verdict"),
    [
        # Blood types O, AB, A, B: "A" is the type A, not the letter A (O) (review, 2026-11-14).
        ("A", "a", "Mixed 1: the answer given, A, is wrong; the right answer is AB."),
        ("a.", "other", "Mixed 1: the answer given, A, is wrong; the right answer is AB."),
        # No option's words are the whole message: the read's letter stands.
        ("is it A?", "a", "Mixed 1: the answer given, O, is wrong; the right answer is AB."),
        # The phone shows no letters: "b" on this card is the type B.
        ("b", "b", "Mixed 1: the answer given, B, is wrong; the right answer is AB."),
        ("B, the second one", "b", "Mixed 1: the answer given, AB, is right."),
    ],
)
@pytest.mark.asyncio
async def test_an_options_own_words_beat_its_letter(content: str, pick: str, verdict: str) -> None:
    card = (
        "```quiz\n"
        '{"label": "Mixed 1", "question": "Universal recipient?", "options": ["O", "AB", "A", '
        '"B"], "answer": 1}\n```'
    )
    recent = [SimpleNamespace(role="assistant", content=f"One more.\n\n{card}")]
    ctx = _turn(content, _card_read([pick]), recent_messages=recent)
    await decide_from_the_read(ctx, _SETTINGS)
    assert verdict in _note(ctx)


@pytest.mark.parametrize(
    ("follow", "laid_out"),
    [
        # "is it 35 or 52?" replies to the card and answers nothing: talked through. It came
        # back Given to Answer on every try (review, 2026-11-14).
        ("answer", False),
        # A new problem asked after the card stands alone, and keeps its layout.
        ("none", True),
        ("solve", True),
    ],
)
@pytest.mark.asyncio
async def test_a_reply_to_the_card_that_answers_nothing_is_not_laid_out(
    follow: str, laid_out: bool
) -> None:
    read = _card_read(["none"], answers=False, goes_on=False, follow=follow)
    ctx = _turn("is it 35 or 52?", read, recent_messages=_AFTER_CARD, worked=WorkedLayout())
    ctx.prompt_messages = with_worked_contract(ctx.prompt_messages)
    await decide_from_the_read(ctx, _SETTINGS)
    assert (ctx.worked is not None) is laid_out
    assert any("```worked" in str(m.get("content")) for m in ctx.prompt_messages) is laid_out


@pytest.mark.parametrize("lesson", [False, True], ids=["cards", "lesson"])
@pytest.mark.asyncio
async def test_a_question_that_names_an_option_is_not_graded(lesson: bool) -> None:
    """ "can you explain why 18 is wrong" names option C as plainly as "18" does; graded, the
    next lesson followed it (review, 2026-11-14). The read says it gives no answer."""
    trace = begin_turn_trace("new")
    content = "can you explain why 18 is wrong"
    card = _LESSON_ONE.split("### Your turn")[1]
    recent = [SimpleNamespace(role="assistant", content=_LESSON_ONE if lesson else card)]
    ctx = _turn(content, _card_read(["c"], answers=False, goes_on=True), recent_messages=recent)
    await decide_from_the_read(ctx, _SETTINGS)
    assert "read.quiz_answer" not in trace.prompt_rules
    assert "read.lesson_next" not in trace.prompt_rules
    aside = any(m["content"] == LESSON_ASIDE_NOTE for m in ctx.prompt_messages)
    assert aside is lesson


_LESSON_ONE = (
    "### Lesson 1: Atoms\n\n### 1. The idea\n\nProtons and neutrons make the nucleus.\n\n"
    "### Your turn\n\n```quiz\n"
    '{"label": "Exercise 1", "question": "17 protons and 18 neutrons: mass number?", '
    '"options": ["17", "35", "18"], "answer": 1}\n```\n\n'
    "Want to try a harder one, or move on to ions?"
)


@pytest.mark.parametrize(
    ("content", "picks", "goes_on", "next_lesson", "graded"),
    [
        ("woah thats a lot lol. ok is it 35?", ["b"], True, True, True),
        ("ok next", ["none"], True, True, False),
        # A pick among the choices the reply offered, or a yes to another offer: neither
        # (review, 2026-11-14: "the first one" was graded "Correct!" and Lesson 2 followed).
        ("the first one", ["none"], False, False, False),
        ("yes", ["none"], False, False, False),
        # A question of its own after the lesson is answered as itself.
        ("why is the electron not in the nucleus?", ["none"], False, False, False),
        # The lesson just above, asked for again, is pointed to, never taught on.
        ("lets start with lesson 1", ["none"], True, False, False),
        # No read of the cards: the system prompt's steps stand.
        ("yes", None, None, False, False),
        # A question between two answers names none and goes on with nothing.
        ("is it 35 or 52?", ["none"], False, False, False),
    ],
)
@pytest.mark.asyncio
async def test_only_an_answer_or_a_go_on_gets_the_next_lesson(
    content: str, picks: list[str] | None, goes_on: bool | None, next_lesson: bool, graded: bool
) -> None:
    trace = begin_turn_trace("new")
    recent = [
        SimpleNamespace(role="user", content="teach me atoms"),
        SimpleNamespace(role="assistant", content=_LESSON_ONE),
    ]
    ctx = _turn(content, _card_read(picks, goes_on=goes_on), recent_messages=recent)
    await decide_from_the_read(ctx, _SETTINGS)
    contract = lesson_next_contract(1)
    assert any(m["content"] == contract for m in ctx.prompt_messages) is next_lesson
    assert ("read.lesson_next" in trace.prompt_rules) is next_lesson
    assert prompt_lesson_layout(ctx.prompt_messages) == ("next" if next_lesson else None)
    assert ("read.quiz_answer" in trace.prompt_rules) is graded
    # What the read says is no answer and no go-on gets the aside note: do that instead.
    aside = goes_on is False and content != "lets start with lesson 1"
    assert any(m["content"] == LESSON_ASIDE_NOTE for m in ctx.prompt_messages) is aside
    assert ctx.prompt_messages[-1] == {"role": "user", "content": content}


@pytest.mark.asyncio
async def test_a_regenerate_grades_the_card_the_message_answered() -> None:
    """Lesson 1's card, "b", then a regenerate of Lesson 2: the pick is Lesson 1's, graded
    against its options, and Lesson 2 is asked for again, never Lesson 3 (review of #2456)."""
    from uuid import uuid4

    from app.modules.chat.turn_prep.context import RegenerateBackup

    redone = SimpleNamespace(
        id=uuid4(),
        role="assistant",
        content=_LESSON_ONE.replace("Lesson 1: Atoms", "Lesson 2: Ions")
        .replace('"17", "35", "18"', '"Na+", "Cl+", "Mg-"')
        .replace("Exercise 1", "Exercise 2"),
    )
    recent = [
        SimpleNamespace(id=uuid4(), role="user", content="teach me atoms"),
        SimpleNamespace(id=uuid4(), role="assistant", content=_LESSON_ONE),
        SimpleNamespace(id=uuid4(), role="user", content="b"),
        redone,
    ]
    trace = begin_turn_trace("new")
    ctx = _turn("b", _card_read(["b"], goes_on=True), recent_messages=recent)
    ctx.regenerate_backup = RegenerateBackup(
        content=redone.content, model=None, message_id=redone.id
    )
    await decide_from_the_read(ctx, _SETTINGS)
    assert "read.quiz_answer" in trace.prompt_rules
    assert "35" in _note(ctx) and "Na+" not in _note(ctx)
    assert any(m["content"] == lesson_next_contract(1) for m in ctx.prompt_messages)
    assert not any(m["content"] == lesson_next_contract(2) for m in ctx.prompt_messages)


@pytest.mark.asyncio
async def test_a_word_lesson_is_followed_by_more_words() -> None:
    """Owner, 2026-11-15: after ten idioms, "ok" gave Lesson 2 as three sections named for
    themes ("Money idioms") whose examples held no idiom. The next lesson keeps the words
    shape when the last lesson taught words, and stays a concept lesson otherwise."""
    idioms = (
        "### Lesson 1: Idioms\n\n"
        + "\n\n".join(
            f"### {n}. Phrase {n}\n\n**Meaning:** m{n}\n\n**Example:** e{n}" for n in range(1, 4)
        )
        + '\n\n### Your turn\n\n```quiz\n{"question": "q?", "options": ["a", "b"], "answer": 0}\n```'
    )
    for lesson, words in ((idioms, True), (_LESSON_ONE, False)):
        recent = [SimpleNamespace(role="assistant", content=lesson)]
        ctx = _turn("ok", _card_read(["none"], goes_on=True), recent_messages=recent)
        await decide_from_the_read(ctx, _SETTINGS)
        expected = lesson_next_contract(1, words=words)
        assert any(m["content"] == expected for m in ctx.prompt_messages)
