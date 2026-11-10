"""The problem "do it" means, the assistant's too: a fast model's read (``chat.posed_read``)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.chat import posed_read
from app.modules.chat.posed_read import Posed, PosedPick, held_restatement, read_posed

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


@pytest.mark.parametrize(
    ("line", "pairs"),
    [
        ("Do it", [("user", "hi"), ("assistant", "Hello! How can I help")]),
        ("Do it", [("user", _CAR)]),
        ("Can you also tell me how fast that is in kilometres per hour and why", _POSED_CHAT),
    ],
)
@pytest.mark.asyncio
async def test_a_line_after_no_reply_that_asks_or_counts_is_not_read(
    line: str, pairs: list[tuple[str, str]]
) -> None:
    posed, model = await _read(line, PosedPick(kind="solve", message=1), pairs)
    assert posed is None
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_change_carries_the_restatement_it_holds_to() -> None:
    pick = PosedPick(
        kind="change",
        message=2,
        problem=_CAR,
        changed="A car travels 120 meters in 10 seconds. What is its speed?",
    )
    posed, _model = await _read("What if it took 10 s?", pick)
    assert posed == Posed(
        problem=_CAR,
        reply=_POSED_CHAT[1][1],
        changed=True,
        restated="A car travels 120 meters in 10 seconds. What is its speed?",
    )


_MASS = "What is the mass of 3.5 mol of H2SO4 in grams"


@pytest.mark.parametrize(
    ("problem", "line", "restated", "held"),
    [
        # The new value replaces the one it changes.
        (
            _MASS,
            "What if n was 1.5 mol instead?",
            "What is the mass of 1.5 mol of H2SO4 in grams",
            True,
        ),
        # A subscript is no value: T_1 is the first temperature.
        (
            "A gas has a volume of 2 L at 27 C. What volume will it have at 127 C?",
            "What if $T_1$ was 300 K?",
            "A gas has a volume of 2 L at 300 K. What volume will it have at 127 C?",
            True,
        ),
        # A sign is part of the value.
        (
            "line parallel to y = -2x + 7 through (1, 1)",
            "What if the line was $y = 2x + 7$?",
            "line parallel to y = 2x + 7 through (1, 1)",
            True,
        ),
        # Another quantity of the same setup keeps every value.
        (
            "what is the y intercept of the line 4x - 2y = 8",
            "How do I find the x-intercept?",
            "what is the x intercept of the line 4x - 2y = 8",
            True,
        ),
        # Tacked on, the new value changes nothing a solver reads.
        (_MASS, "What if M was 50 g/mol?", f"{_MASS} if M was 50 g/mol?", False),
        # A value worked out by the model is no restatement.
        (
            _MASS,
            "What if it was 3 times more?",
            "What is the mass of 10.5 mol of H2SO4 in grams",
            False,
        ),
        # No value to put in: "what if gravity was weaker?" is the model's to answer.
        (_MASS, "What if it was less?", "What is the mass of less H2SO4 in grams", False),
        # Words neither the problem nor the line holds.
        (
            _MASS,
            "What if n was 1.5 mol?",
            "Find the volume at standard temperature and pressure of 1.5 mol of H2SO4 gas",
            False,
        ),
        (_MASS, "What if n was 1.5 mol?", _MASS, False),
        (_MASS, "What if n was 1.5 mol?", None, False),
    ],
)
def test_held_restatement(problem: str, line: str, restated: str | None, held: bool) -> None:
    assert (held_restatement(problem, line, restated) is not None) is held


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
