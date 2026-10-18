""" "What if the coefficient was 2?" rebuilds the last equation for the verified solver."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.math.followup import restated_math_problem
from app.modules.math.followup_what_if import is_part_change
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.prompt import build_math_augmentation


def _history(prior: str) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(role="user", content=prior),
        SimpleNamespace(role="assistant", content="x = ..."),
    ]


@pytest.mark.parametrize(
    ("query", "prior", "rebuilt"),
    [
        ("What if coefficient was 2?", "3x+5=0", "2x + 5 = 0"),
        ("what if the coefficient of x was 4", "3x+5=0", "4x + 5 = 0"),
        ("what if the constant was 7", "3x+5=0", "3x + 7 = 0"),
        ("what if the right side was 10", "3x+5=0", "3x + 5 = 10"),
        ("what if it was 5?", "3x+3=3", "3x + 3 = 5"),
        ("what if it equalled 9", "2x+1=5", "2x + 1 = 9"),
        # A whole new equation is still a restatement.
        ("what if it was 2x + 5 = 21?", "3x+5=0", "2x + 5 = 21"),
    ],
)
def test_a_part_change_rebuilds_the_last_equation(query: str, prior: str, rebuilt: str) -> None:
    assert restated_math_problem(query, _history(prior)) == rebuilt


@pytest.mark.parametrize(
    ("query", "prior"),
    [
        # A quadratic has two coefficients; "the coefficient" does not say which.
        ("what if the coefficient was 2", "x^2-5x+6=0"),
        # No y in the equation.
        ("what if the coefficient of y was 2", "3x+5=0"),
        # No equation before it.
        ("What if coefficient was 2?", "what is the capital of france"),
    ],
)
def test_a_part_change_with_nothing_to_change_is_left_alone(query: str, prior: str) -> None:
    assert restated_math_problem(query, _history(prior)) is None


@pytest.mark.asyncio
async def test_the_rebuilt_equation_gets_the_verified_lesson() -> None:
    query = "What if coefficient was 2?"
    assert is_part_change(query)
    problem = restated_math_problem(query, _history("3x+5=0"))
    assert problem is not None
    _, verified = await build_math_augmentation(problem, Settings(math_tools_enabled=True))
    reply = maybe_direct_math_reply(verified, query, verified_request_text=problem)
    assert reply is not None
    assert "**1. Subtract 5 from both sides** — Subtraction property of equality" in reply
    assert reply.count("```answer") == 1
