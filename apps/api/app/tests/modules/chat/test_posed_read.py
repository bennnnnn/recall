"""The problem "do it" means, the assistant's too: a fast model's read (``chat.posed_read``)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.chat import posed_read
from app.modules.chat.posed_read import Posed, PosedPick, read_posed

# The read asks the subject of the exchange before it in the SymPy pool.
pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_CAR = "A car travels 120 meters in 20 seconds. What is its speed?"
_POSED_CHAT = [
    ("user", "Give me physics question for grade 7th"),
    (
        "assistant",
        "Sure! A car travels **120 meters in 20 seconds**. What is its speed? \U0001f697",
    ),
]


def _rows(pairs: list[tuple[str, str]]) -> list[SimpleNamespace]:
    return [SimpleNamespace(role=role, content=content) for role, content in pairs]


async def _read(
    line: str, pick: PosedPick | None, pairs: list[tuple[str, str]] = _POSED_CHAT
) -> tuple[Posed | None, AsyncMock]:
    model = AsyncMock(return_value=pick)
    with patch.object(posed_read, "pick_posed", model):
        return await read_posed(Settings(), line, _rows(pairs)), model


@pytest.mark.asyncio
async def test_do_it_is_the_problem_the_assistant_posed() -> None:
    posed, model = await _read("Do it", PosedPick(kind="solve", message=2, problem=_CAR))
    assert posed == Posed(problem=_CAR, reply=_POSED_CHAT[1][1])
    assert model.await_args is not None
    conversation = model.await_args.args[2]
    # The assistant's messages are numbered too: the problem may be theirs.
    assert "[2] Assistant: Sure! A car travels **120 meters" in conversation


@pytest.mark.asyncio
async def test_a_problem_a_reply_does_not_hold_word_for_word_is_none() -> None:
    """The model's copy is checked against the reply; a reply is never taken whole."""
    made_up = PosedPick(kind="solve", message=2, problem="A car travels 150 m in 20 s.")
    assert (await _read("Do it", made_up))[0] is None
    # A user's message is the problem as typed, whatever the copy says.
    typed = [("user", _CAR), ("assistant", "6 m/s")]
    posed, _model = await _read("Step by step", PosedPick(kind="solve", message=1), typed)
    assert posed is not None and posed.problem == _CAR


@pytest.mark.parametrize(
    "pick",
    [
        None,
        PosedPick(kind="answer"),
        PosedPick(kind="other"),
        PosedPick(kind="solve", message=None),
        PosedPick(kind="solve", message=7, problem=_CAR),
    ],
)
@pytest.mark.asyncio
async def test_no_read_an_answer_or_an_offer_is_no_solve(pick: PosedPick | None) -> None:
    assert (await _read("do it", pick))[0] is None


_HISTORY_CHAT = [
    ("user", "When did World War II end?"),
    ("assistant", "It ended in 1945. Anything else?"),
]


@pytest.mark.parametrize(
    ("line", "pairs"),
    [
        ("Do it", [("user", _CAR)]),
        ("Can you also tell me how fast that is in kilometres per hour and why", _POSED_CHAT),
        # The review of aef64c847: after a reply with a number and a question but no
        # problem, every short line waited on the read.
        *(
            (line, _HISTORY_CHAT)
            for line in (
                "Who was the US president then?",
                "Tell me a joke",
                "Translate hello to French",
                "What's the weather in Paris?",
                "write a haiku about rain",
            )
        ),
        ("do it", [("user", "help me study"), ("assistant", "Want me to make a study plan?")]),
    ],
)
@pytest.mark.asyncio
async def test_a_line_after_an_exchange_with_no_problem_is_not_read(
    line: str, pairs: list[tuple[str, str]]
) -> None:
    posed, model = await _read(line, PosedPick(kind="solve", message=1), pairs)
    assert posed is None
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_line_after_a_solved_problem_is_read() -> None:
    """The exchange's problem may be the user's, the reply its answer (a tapped what-if)."""
    typed = [("user", _CAR), ("assistant", "**Given** d = 120 m, t = 20 s ... v = 6 m/s")]
    pick = PosedPick(kind="change", message=1, problem=_CAR, given="20 seconds", new="10 s")
    posed, model = await _read("What if it took 10 s?", pick, typed)
    model.assert_awaited_once()
    assert posed == Posed(
        problem=_CAR, reply=typed[1][1], changed=True, given="20 seconds", new="10 s"
    )


@pytest.mark.asyncio
async def test_a_new_value_the_line_does_not_give_is_none() -> None:
    pick = PosedPick(kind="change", message=2, problem=_CAR, given="20 seconds", new="12 s")
    posed, _model = await _read("What if it took 10 s?", pick)
    assert posed is not None and posed.new is None


@pytest.mark.asyncio
async def test_the_read_is_kept_for_the_turn() -> None:
    from app.core import readings

    readings.begin_turn()
    model = AsyncMock(return_value=PosedPick(kind="solve", message=2, problem=_CAR))
    rows: list[Any] = _rows(_POSED_CHAT)
    with patch.object(posed_read, "pick_posed", model):
        first = await posed_read.posed_for_turn(Settings(), "Do it", rows)
        again = await posed_read.posed_for_turn(Settings(), "Do it", rows)
    assert first == again and first is not None
    model.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_replys_cheer_after_the_problem_is_left_out() -> None:
    """A copy that runs on into "Give it a try!" is the problem without it, as typed."""
    chat = [
        ("user", "Give me a maths practice problem"),
        ("assistant", "Solve for x: 3x + 5 = 20. Give it a try! You've got this!"),
    ]
    pick = PosedPick(kind="solve", message=2, problem=chat[1][1])
    posed, _model = await _read("what's the answer", pick, chat)
    assert posed is not None and posed.problem == "Solve for x: 3x + 5 = 20."


@pytest.mark.asyncio
async def test_a_look_at_the_reply_that_gives_up_leaves_the_turns_readings() -> None:
    """The re-review of 35970e984: the look ran in the turn's own readings, so a pool that
    gave up on it declined them all and the turn's own solve read nothing."""
    from app.core import readings

    readings.begin_turn()
    model = AsyncMock(return_value=PosedPick(kind="solve", message=2, problem=_CAR))
    with (
        patch("app.core.sympy_executor.run_sympy", AsyncMock(side_effect=TimeoutError)),
        patch.object(posed_read, "pick_posed", model),
    ):
        assert await read_posed(Settings(), "Do it", _rows(_POSED_CHAT)) is None
    model.assert_not_awaited()
    assert not readings.readings_declined()
    assert await readings.read_off_loop(len, "abc", timeout=5) == 3


@pytest.mark.asyncio
async def test_stop_cancels_the_read() -> None:
    """The read runs inside the turn: Stop cancelling the turn cancels the model call."""
    asked = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(*_args: Any) -> PosedPick:
        asked.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        raise AssertionError("never answered")

    with patch.object(posed_read, "pick_posed", slow):
        turn = asyncio.create_task(read_posed(Settings(), "Do it", _rows(_POSED_CHAT)))
        await asyncio.wait_for(asked.wait(), timeout=5)
        turn.cancel()
        with pytest.raises(asyncio.CancelledError):
            await turn
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_a_regenerate_reads_the_chat_without_the_reply_it_redoes() -> None:
    """The review of aef64c847: regenerating "Do it" showed the read the answer being
    replaced as the latest reply, so the problem's reply was the old answer."""
    from typing import cast
    from uuid import uuid4

    from app.modules.chat.turn_prep.augment import reads_window
    from app.modules.chat.turn_prep.request import TurnRequest

    rows = [
        SimpleNamespace(id=uuid4(), role=role, content=content)
        for role, content in (*_POSED_CHAT, ("user", "Do it"), ("assistant", "6 m/s."))
    ]
    request = cast(
        "TurnRequest",
        SimpleNamespace(recent_messages=rows, omit_message_ids={rows[-1].id}, content="Do it"),
    )
    model = AsyncMock(return_value=PosedPick(kind="solve", message=2, problem=_CAR))
    with patch.object(posed_read, "pick_posed", model):
        posed = await read_posed(Settings(), "Do it", reads_window(request))
    assert posed == Posed(problem=_CAR, reply=_POSED_CHAT[1][1])
    assert model.await_args is not None
    assert "6 m/s." not in model.await_args.args[2]
