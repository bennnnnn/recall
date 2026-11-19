"""One read for what a short follow-up line is about, for the reply and the questions under it
(``chat.follow_up_read``).

A 53-turn Grade 8 physics chat (2026-11-18): "explain step 2" after a water-pressure answer
explained Newton's second law from seven turns back, "and b?" answered half of part b, and
the questions under three replies were about the problem before. The posed read that names
the message failed validation on 7 of 12 calls: it answered "changes": null.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core import readings
from app.core.config import Settings
from app.models.orm import User
from app.modules.chat import posed_read
from app.modules.chat.follow_up_read import (
    FollowUp,
    follow_up_for_turn,
    follow_up_from,
    followed_for_questions,
    note_the_follow_up,
)
from app.modules.chat.follow_up_thread import Followed, thread_problem
from app.modules.chat.posed_read import PosedPick, read_posed, start_posed_read
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.tests.fakes import isolated_settings

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_LAMP = (
    "A 75Ω lamp and 150Ω heater are connected in parallel across a 150V potential difference.\n"
    "a) What is the equivalent resistance of the two items?\n"
    "b) Find the currents flowing through the two items.\n"
    "c) What current flows through the entire circuit?\n"
    "just do a first"
)
_WATER = (
    "A rectangular container of base 50 cm by 30 cm is filled with water to a depth of 5 cm. "
    "How much is the pressure exerted at the base?"
)
_WATER_REPLY = "**Given** h = 0.05 m\n\n**Substitution** P = 1000 × 10 × 0.05\n\nP = 500 Pa"
_CHAT = [
    ("user", "State and explain the three Newton's laws of motion."),
    ("assistant", "1. First law ... 2. Second law: F = ma ... 3. Third law ..."),
    ("user", _WATER),
    ("assistant", _WATER_REPLY),
]


def _rows(pairs: list[tuple[str, str]]) -> list[SimpleNamespace]:
    return [SimpleNamespace(role=role, content=content) for role, content in pairs]


def test_a_null_list_of_changes_is_none() -> None:
    """The prompt's "otherwise" case: read as a failure, it voided the whole read."""
    pick = PosedPick.model_validate(
        {"kind": "other", "message": None, "problem": None, "changes": None}
    )
    assert pick.changes == []


def test_a_copy_past_its_cap_is_none_and_the_read_stands() -> None:
    pick = PosedPick.model_validate(
        {"kind": "explain", "message": 4, "part": "step 2", "problem": "x" * 700}
    )
    assert (pick.problem, pick.part, pick.message) == (None, "step 2", 4)


@pytest.mark.parametrize(
    ("pick", "expected"),
    [
        # "explain step 2": the answer just above, its step in the line's words.
        (
            PosedPick(kind="explain", message=4, part="step 2"),
            FollowUp("explain", "assistant", _WATER_REPLY, _WATER, None, "step 2", None),
        ),
        # A part the message labels: its own words are quoted.
        (
            PosedPick(kind="solve", message=1, part="(b)"),
            FollowUp(
                "solve",
                "user",
                _LAMP,
                None,
                None,
                "b",
                "Find the currents flowing through the two items.",
            ),
        ),
        # A label no message has names nothing; the message still stands.
        (
            PosedPick(kind="solve", message=1, part="e"),
            FollowUp("solve", "user", _LAMP, None, None, None, None),
        ),
    ],
)
def test_the_read_is_held_to_the_chat(pick: PosedPick, expected: FollowUp) -> None:
    chat = _CHAT if pick.kind == "explain" else [("user", _LAMP), ("assistant", "R = 50 Ω")]
    assert follow_up_from(pick, chat) == expected


@pytest.mark.parametrize(
    "pick",
    [
        None,
        PosedPick(kind="other", message=4),
        PosedPick(kind="answer", message=4),
        PosedPick(kind="explain", message=None),
        PosedPick(kind="explain", message=9),
    ],
)
def test_no_message_named_is_no_follow_up(pick: PosedPick | None) -> None:
    assert follow_up_from(pick, _CHAT) is None


def test_a_reply_the_line_follows_is_the_problem_it_answered() -> None:
    follow = follow_up_from(PosedPick(kind="explain", message=4), _CHAT)
    assert follow is not None and follow.problem == _WATER


@pytest.mark.asyncio
async def test_the_read_begun_as_the_turn_loads_is_the_solves_too() -> None:
    """One call: the solve after the prep takes the read begun beside it."""
    readings.begin_turn()
    pairs = [("user", _LAMP), ("assistant", "**Answer** R = 50 Ω")]
    pick = PosedPick(kind="solve", message=1, part="b")
    model = AsyncMock(return_value=pick)
    with patch.object(posed_read, "pick_posed", model):
        start_posed_read(Settings(), "and b?", _rows(pairs))
        posed = await read_posed(Settings(), "and b?", _rows(pairs))
        follow = await follow_up_for_turn("and b?", seconds=1.0)
    assert model.await_count == 1
    # Part b alone, never every part again: the statement and b's own words.
    assert posed is not None and posed.problem == (
        "A 75Ω lamp and 150Ω heater are connected in parallel across a 150V potential "
        "difference. Find the currents flowing through the two items."
    )
    assert follow is not None and follow.part_text == (
        "Find the currents flowing through the two items."
    )


def _turn(content: str, read: TurnDecision | None) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            {"role": "system", "content": "rules"},
            {"role": "user", "content": _WATER},
            {"role": "assistant", "content": _WATER_REPLY},
            {"role": "user", "content": content},
        ],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )
    ctx.user = User(id=uuid4(), email="a@b.c", plan="pro")
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result(read)
    ctx.live_read = future  # type: ignore[assignment]
    return ctx


@pytest.mark.asyncio
async def test_the_reply_is_told_which_message_and_step_the_line_follows() -> None:
    readings.begin_turn()
    trace = begin_turn_trace("new")
    model = AsyncMock(return_value=PosedPick(kind="explain", message=4, part="step 2"))
    with patch.object(posed_read, "pick_posed", model):
        start_posed_read(isolated_settings(), "explain step 2", _rows(_CHAT))
        ctx = _turn("explain step 2", None)
        loop = asyncio.get_running_loop()
        await note_the_follow_up(ctx, isolated_settings(), loop.time() + 1.0)
    note = ctx.prompt_messages[-2]
    assert note["role"] == "system"
    assert note["content"].startswith('This message follows up your reply to "A rectangular')
    assert '"step 2"' in note["content"]
    assert ctx.prompt_messages[-1] == {"role": "user", "content": "explain step 2"}
    assert "follow_up.explain" in trace.prompt_rules


@pytest.mark.asyncio
async def test_no_read_says_nothing() -> None:
    readings.begin_turn()
    ctx = _turn("explain step 2", None)
    before = list(ctx.prompt_messages)
    await note_the_follow_up(ctx, isolated_settings(), asyncio.get_running_loop().time() + 0.1)
    assert ctx.prompt_messages == before


def _read(follow: str) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": "physics", "think": False, "follow": follow}
    )


@pytest.mark.asyncio
async def test_the_questions_follow_the_named_problem_or_none_for_a_line_alone() -> None:
    readings.begin_turn()
    # The turn's read says the line stands alone: the questions follow no earlier problem.
    assert followed_for_questions(_turn("Explain scientific notation.", _read("none"))) == (
        Followed(None)
    )
    # Neither read answered: the questions are chosen as before.
    assert followed_for_questions(_turn("why?", _read("explain"))) is None
    # The follow-up read named a message: its problem.
    model = AsyncMock(return_value=PosedPick(kind="explain", message=4))
    with patch.object(posed_read, "pick_posed", model):
        start_posed_read(isolated_settings(), "why?", _rows(_CHAT))
        await follow_up_for_turn("why?", seconds=1.0)
    assert followed_for_questions(_turn("why?", _read("explain"))) == Followed(_WATER)


_COINS = (
    "When 10 similar coins are dropped into a graduated cylinder the level of the water rose "
    "from 75 mL to 100 mL. What is the average volume of each coin?"
)


def test_a_line_the_read_says_stands_alone_follows_no_earlier_problem() -> None:
    """ "Explain the advantage of using scientific notation." after the coins kept the coins'
    questions (t03): the word rules walked back to the last line naming a subject."""
    prior = _rows([("user", _COINS), ("assistant", "Each coin is 2.5 mL.")])
    line = "Explain the advantage of using scientific notation."
    assert thread_problem(line, prior) == _COINS
    assert thread_problem(line, prior, followed=Followed(None)) is None
    assert thread_problem("why?", prior, followed=Followed(_COINS)) == _COINS
    # A followed message that is no subject problem gives none.
    assert thread_problem("why?", prior, followed=Followed("thanks a lot")) is None


@pytest.mark.asyncio
async def test_a_begun_read_leaves_the_turns_readings_to_the_pool() -> None:
    """The turn's readings go to the SymPy pool; the begun call stays on the loop. Kept as a
    task, it failed to pickle and every reading of the turn was declined (live, 2026-11-18)."""
    import pickle

    readings.begin_turn()
    with patch.object(posed_read, "pick_posed", AsyncMock(return_value=None)):
        start_posed_read(Settings(), "and b?", _rows([("user", _LAMP), ("assistant", "50 Ω")]))
        copied = pickle.loads(pickle.dumps(readings._MEMO.get()))  # noqa: S301 - our own
        assert posed_read.posed_started("and b?") is not None
    assert [value.task for value in copied.values()] == [None]


@pytest.mark.asyncio
async def test_small_talk_waits_for_no_read() -> None:
    """A light turn takes the read only when it is already in; it never holds the reply."""
    readings.begin_turn()
    slow = asyncio.Event()

    async def late(*_args: Any) -> PosedPick:
        await slow.wait()
        return PosedPick(kind="explain", message=4)

    with patch.object(posed_read, "pick_posed", late):
        start_posed_read(isolated_settings(), "ok thanks", _rows(_CHAT))
        ctx = _turn("ok thanks", None)
        ctx.lightweight_turn = True
        loop = asyncio.get_running_loop()
        started = loop.time()
        await note_the_follow_up(ctx, isolated_settings(), started + 5.0)
        assert loop.time() - started < 0.5
        slow.set()
        posed_read.stop_posed_read()
    assert ctx.prompt_messages[-2]["content"] == _WATER_REPLY


@pytest.mark.asyncio
async def test_a_lesson_step_reads_the_reply_its_own_way() -> None:
    readings.begin_turn()
    lesson = "## Lesson 1: Pressure\n\nPressure is force per area.\n\nReady for Lesson 2?"
    model = AsyncMock(return_value=PosedPick(kind="explain", message=2))
    rows = _rows([("user", "teach me pressure"), ("assistant", lesson)])
    with patch.object(posed_read, "pick_posed", model):
        start_posed_read(isolated_settings(), "why?", rows)
        ctx = _turn("why?", None)
        ctx.recent_messages = rows
        before = list(ctx.prompt_messages)
        await note_the_follow_up(ctx, isolated_settings(), asyncio.get_running_loop().time() + 1)
    assert ctx.prompt_messages == before


def test_a_reply_whose_question_was_not_shown_is_no_problem() -> None:
    follow = follow_up_from(PosedPick(kind="explain", message=1), [("assistant", _WATER_REPLY)])
    assert follow is not None and follow.problem is None
