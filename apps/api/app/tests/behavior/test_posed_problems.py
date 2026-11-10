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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "reply", "line", "changed", "answer"),
    [
        (
            "max (Carnot) efficiency of a heat engine working between 500 K and 300 K?",
            "**Answer**\n\n```answer\n0.4\n```",
            "What if $T_C = 200\\,\\mathrm{K}$?",
            "max (Carnot) efficiency of a heat engine working between 500 K and 200 K?",
            "0.6",
        ),
        (
            "how much water if 3.0 g of hydrogen and 16.0 g of oxygen react",
            "**Answer**\n\n```answer\nLimiting reagent = O2; 18 g H2O\n```",
            "What if O₂ mass was 32.0 g?",
            "how much water if 3.0 g of hydrogen and 32.0 g of oxygen react",
            "H2",
        ),
    ],
)
async def test_tapped_what_if_solved_as_typed(
    question: str, reply: str, line: str, changed: str, answer: str, thread_sympy_executor: None
) -> None:
    """A tapped follow-up question changes one value: the problem with it, solved as typed."""
    typed = await _route(changed)
    followed = await _route(
        line,
        history=(("user", question), ("assistant", reply)),
        posed=question,
        posed_changed=changed,
    )
    assert answer in followed.verified_answer
    assert decision_record(followed)["solver"] == decision_record(typed)["solver"]
    assert followed.instant_text == typed.instant_text


@pytest.mark.asyncio
async def test_without_a_read_the_posed_problem_is_not_guessed(thread_sympy_executor: None) -> None:
    """No model, no read: "Do it" is the model's to answer, as before."""
    history = (("user", _POSED[0][2]), ("assistant", _POSED[0][3]))
    assert not (await _route("Do it", history=history)).solved
