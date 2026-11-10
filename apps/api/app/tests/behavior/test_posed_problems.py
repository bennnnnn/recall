"""A problem the assistant posed is solved as the same problem typed (``chat.posed_read``).

The owner's chat (2026-11-10): typed, "A car travels 120 meters in 20 seconds. What is its
speed?" got the physics solver's Given / Required / formula / substitution and a verified
card; "Do it" after the assistant posed that question got "Answer: 6 meters per second".
Each line below, after the posed question, must decide what the typed question decides:
the same solver, the same operation, verified, and the same reply.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.subjects.registry import SubjectName, subject_adapter
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.decisions import decision_record
from app.tests.behavior.harness import Route, route_case

_POSED = (
    (
        "physics",
        "A car travels 120 meters in 20 seconds. What is its speed?",
        "Give me physics question for grade 7th",
        "A car travels **120 meters in 20 seconds**. What is its speed? \U0001f697",
    ),
    (
        "chemistry",
        "How many moles are in 36 g of water (H2O)?",
        "Give me a chemistry practice question",
        "How many moles are in 36 g of water (H2O)? Give it a go!",
    ),
    (
        "math",
        "Solve for x: 3x + 5 = 20.",
        "Give me a maths practice problem",
        "Solve for x: 3x + 5 = 20. Give it a try!",
    ),
)
_LINES = ("Do it", "solve it", "How", "Step by step", "what's the answer")


async def _route(prompt: str, **kwargs: Any) -> Route:
    return await route_case(Case("posed", "physics", prompt, Expect(), "", **kwargs))


@pytest.mark.asyncio
@pytest.mark.parametrize(("subject", "question", "ask", "posed"), _POSED)
@pytest.mark.parametrize("line", _LINES)
async def test_posed_problem_solved_as_typed(
    subject: str, question: str, ask: str, posed: str, line: str, thread_sympy_executor: None
) -> None:
    typed = await _route(question)
    followed = await _route(line, history=(("user", ask), ("assistant", posed)), posed=question)
    assert typed.solved and typed.instant == "solver", subject
    assert decision_record(followed)["solver"] == decision_record(typed)["solver"]
    assert followed.verified_answer == typed.verified_answer
    assert followed.instant_text == typed.instant_text


_CARNOT = "max (Carnot) efficiency of a heat engine working between 500 K and 300 K?"
_WATER = "how much water if 3.0 g of hydrogen and 16.0 g of oxygen react"
_CAR = "A car travels 120 meters in 20 seconds. What is its speed?"
_BALL = "A 2 kg ball moves at 3 m/s. What is its kinetic energy?"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "line", "change", "typed"),
    [
        (
            _CARNOT,
            "What if $T_C = 200\\,\\mathrm{K}$?",
            ("300 K", "200 K"),
            "max (Carnot) efficiency of a heat engine working between 500 K and 200 K?",
        ),
        (
            _WATER,
            "What if O\u2082 mass was 32.0 g?",
            ("16.0 g of oxygen", "32.0 g"),
            "how much water if 3.0 g of hydrogen and 32.0 g of oxygen react",
        ),
        # The read names the wrong given: the new value's unit says which one changes, so
        # "10 seconds" is the time, never the 120 meters, and "5 m/s" the speed, never the
        # 2 kg (the review of aef64c847 found both accepted as written).
        (
            _CAR,
            "What if it took 10 seconds?",
            ("120 meters", "10 seconds"),
            "A car travels 120 meters in 10 seconds. What is its speed?",
        ),
        (
            _BALL,
            "And if the speed was 5 m/s instead?",
            ("2 kg", "5 m/s"),
            "A 2 kg ball moves at 5 m/s. What is its kinetic energy?",
        ),
    ],
)
async def test_a_named_change_is_solved_as_the_problem_typed_with_it(
    question: str, line: str, change: tuple[str, str], typed: str, thread_sympy_executor: None
) -> None:
    """A tapped follow-up question changes one value: the server puts it in place of the
    given of its kind and the problem is solved as the user would have typed it."""
    expected = await _route(typed)
    followed = await _route(
        line,
        history=(("user", question), ("assistant", "**Answer** worked above.")),
        posed=question,
        posed_change=change,
    )
    assert expected.solved
    assert followed.verified_answer == expected.verified_answer
    assert decision_record(followed)["solver"] == decision_record(expected)["solver"]


@pytest.mark.parametrize(
    ("subject", "problem", "given", "new"),
    [
        # No given of the new value's kind, or two the read's quote does not tell apart.
        ("physics", _CAR, "the time", "10 kg"),
        ("physics", _CARNOT, "the cold one", "200 K"),
        # A value tacked on that no given of the problem holds ("if M was 50 g/mol").
        ("chemistry", "What is the mass of 3.5 mol of H2SO4 in grams", "molar mass", "50 g/mol"),
        # An expression the problem does not write once.
        ("math", "solve x^2 + x^2 = 8", "x^2", "x^3"),
        ("math", "solve 2x + 3 = 7", "2x + 3 = 7", "5"),
    ],
)
def test_a_change_no_subject_puts_in_place_exactly_is_none(
    subject: SubjectName, problem: str, given: str, new: str
) -> None:
    assert subject_adapter(subject).followups.changed_problem(problem, given, new) is None


@pytest.mark.asyncio
async def test_without_a_read_the_posed_problem_is_not_guessed(thread_sympy_executor: None) -> None:
    """No model, no read: "Do it" is the model's to answer, as before."""
    history = (("user", _POSED[0][2]), ("assistant", _POSED[0][3]))
    assert not (await _route("Do it", history=history)).solved


@pytest.mark.parametrize(
    ("line", "history"),
    [
        ("thanks", (("user", _POSED[0][2]), ("assistant", _POSED[0][3]))),
        ("ok", (("user", _POSED[0][2]), ("assistant", _POSED[0][3]))),
        # A reader claims it: the car's time changed, no read needed.
        ("What if it took 10 s?", (("user", _CAR), ("assistant", "**Answer** 6 m/s"))),
        # Its own problem.
        (
            "A train goes 300 m in 15 s. What is its speed?",
            (("user", _CAR), ("assistant", "6 m/s")),
        ),
    ],
)
@pytest.mark.asyncio
async def test_a_line_the_turn_answers_without_the_read_makes_no_model_call(
    line: str, history: tuple[tuple[str, str], ...], thread_sympy_executor: None
) -> None:
    """The re-review of 35970e984: the read started on nearly every short line after a
    reply. It now runs only where it decides the turn."""
    from unittest.mock import AsyncMock, patch

    from app.modules.chat import posed_read

    model = AsyncMock(return_value=None)
    with patch.object(posed_read, "pick_posed", model):
        await _route(line, history=history)
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_do_it_after_a_posed_problem_makes_the_model_call(
    thread_sympy_executor: None,
) -> None:
    from unittest.mock import AsyncMock, patch

    from app.modules.chat import posed_read

    model = AsyncMock(return_value=None)
    with patch.object(posed_read, "pick_posed", model):
        await _route("Do it", history=(("user", _POSED[0][2]), ("assistant", _POSED[0][3])))
    model.assert_awaited_once()
