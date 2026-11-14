"""Equations are read over the reals: a root outside a logarithm's or an even root's domain is
rejected with why, and a stated real domain keeps no non-real root.

2026-11-13 audit: ``log(x - 5) = log(2x)`` came back a checked x = -5, ``ln(x - 4) = ln(1 - x)``
x = 5/2 and ``sqrt(x - 3) = sqrt(1 - x)`` x = 2 (each holds only over the complex numbers,
MATH-02); "solve x^2 + 1 = 0 over the reals" came back ±i (MATH-03).
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.core.config import Settings
from app.modules.math.schemas import EquationInput
from app.modules.math.solve.equations import solve_equation
from app.modules.math.solve.key_steps import equation_key_steps
from app.modules.math.solve.parse import parse_equation
from app.modules.math.tools.block.algebra import wants_real_roots
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply


async def _reply(text: str) -> tuple[str | None, str | None]:
    """(canonical answer, direct reply) for one turn, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    augmentation = await build_subject_augmentation(text, settings)
    verified = augmentation.verified
    answer = getattr(verified, "canonical_answer", None) if verified is not None else None
    return answer, maybe_direct_subject_reply(verified, text)


def _tidy(roots: Iterable[str]) -> list[str]:
    return sorted(root.replace(" ", "") for root in roots)


@pytest.mark.parametrize(
    ("lhs", "rhs", "kept", "rejected"),
    [
        # Both sides the same function of a negative number: equal only over the complex numbers.
        ("log(x-5)", "log(2x)", [], ["x = -5"]),
        ("ln(x-4)", "ln(1-x)", [], [r"x = \frac{5}{2}"]),
        ("log_3(x-8)", "log_3(2x)", [], ["x = -8"]),
        ("sqrt(x-3)", "sqrt(1-x)", [], ["x = 2"]),
        ("sqrt(2x-5)", "sqrt(x-4)", [], ["x = 1"]),
        # The radicand as written, before SymPy folds sqrt(x)^2 into x.
        ("sqrt(x)^2", "-4", [], ["x = -4"]),
        ("x^(1/4)", "-2", [], []),
        # One root kept, one rejected.
        ("ln(x-1)", "ln(x^2-7)", ["x = 3"], ["x = -2"]),
        # Controls: every root is in the domain.
        ("log(x)+log(x+3)", "log(4)", ["x = 1"], []),
        ("log(x^2)", "log(4)", ["x = -2", "x = 2"], []),
        ("sqrt(x+2)", "x", ["x = 2"], []),
        ("x^(1/4)", "2", ["x = 16"], []),
        ("x^2+4", "0", ["x = - 2 i", "x = 2 i"], []),
        # A parameter leaves the domain undecided: the root stays.
        ("log(x-a)", "log(2)", ["x = a + 2"], []),
    ],
)
def test_a_root_outside_the_real_domain_is_rejected(
    lhs: str, rhs: str, kept: list[str], rejected: list[str]
) -> None:
    result = solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"]))
    assert _tidy(result.solutions_latex) == _tidy(kept)
    assert _tidy(item.root for item in result.rejected_roots) == _tidy(rejected)
    if rejected and not kept:
        assert result.solution_kind == "none"
        assert any("rejected" in step for step in result.steps)


def test_asked_complex_roots_keep_the_complex_solution() -> None:
    """The complex numbers asked for: log(-10) = log(-10) is no domain error there."""
    result = solve_equation(
        EquationInput(lhs="log(x-5)", rhs="log(2x)", variables=["x"], complex_roots=True)
    )
    assert result.solutions_latex == ["x = -5"]
    assert result.rejected_roots == []


@pytest.mark.parametrize(
    ("lhs", "rhs", "kept", "rejected"),
    [
        ("x^2+1", "0", [], ["x = - i", "x = i"]),
        ("x^2+2x+5", "0", [], ["x = - 2 i - 1", "x = 2 i - 1"]),
        # A real root beside non-real ones: they go unsaid, as without a stated domain.
        ("x^3", "8", ["x = 2"], []),
        ("x^2", "4", ["x = -2", "x = 2"], []),
    ],
)
def test_a_stated_real_domain_keeps_no_non_real_root(
    lhs: str, rhs: str, kept: list[str], rejected: list[str]
) -> None:
    result = solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"], real_only=True))
    assert _tidy(result.solutions_latex) == _tidy(kept)
    assert _tidy(item.root for item in result.rejected_roots) == _tidy(rejected)
    assert all("not a real number" in item.why for item in result.rejected_roots)


@pytest.mark.parametrize(
    ("text", "real"),
    [
        ("solve x^2 + 1 = 0 over the reals", True),
        ("solve x^2 + 1 = 0 over the real numbers", True),
        ("solve x^2+1=0 for real x", True),
        ("Find all real x such that x^2 + 9 = 0", True),
        ("find the real solutions of x^2 + 2x + 5 = 0", True),
        ("find the real-number roots of x^2 + 4 = 0", True),
        ("solve x^2+9=0 where x is a real number", True),
        ("solve x^2 + 1 = 0 for x \\in \\mathbb{R}", True),
        ("solve x^2 + 1 = 0, x ∈ ℝ", True),
        ("solve x^2 + 1 = 0 in the reals", True),
        # Look-alikes: no real domain stated.
        ("solve x^2 + 1 = 0", False),
        ("find the non-real roots of x^2 + 1 = 0", False),
        ("find all real and complex roots of x^3 = 8", False),
        ("find the complex roots of x^2 + 4 = 0", False),
        ("what is the real part of z = 3 + 4i", False),
        ("this is a really hard one: x^2 = 4", False),
        ("real numbers are fun, solve 2x = 4", False),
    ],
)
def test_a_stated_real_domain_is_read(text: str, real: bool) -> None:
    assert wants_real_roots(text) is real


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("solve log(x-5) = log(2x)", r"\text{no real solution}"),
        ("solve ln(x-4) = ln(1-x)", r"\text{no real solution}"),
        ("solve sqrt(x-3) = sqrt(1-x)", r"\text{no real solution}"),
        ("solve log_3(x-8)=log_3(2x)", r"\text{no real solution}"),
        ("solve x^2 + 1 = 0 over the reals", r"\text{no real solution}"),
        ("Find all real x such that x^2 + 9 = 0", r"\text{no real solution}"),
        ("solve log(x)+log(x+3)=log(4)", "x = 1"),
        ("solve sqrt(x+2)=x", "x = 2"),
        ("solve x^2+4=0", r"x = \pm 2 i"),
        ("solve x^3 = 8 over the reals", "x = 2"),
    ],
)
async def test_the_turn_answers_over_the_reals(text: str, answer: str) -> None:
    got, _direct = await _reply(text)
    assert got == answer


async def test_the_working_says_why_a_root_is_rejected() -> None:
    """The reason is in the working, as a check of the root: not only "no solution"."""
    _answer, direct = await _reply("solve log(x-5) = log(2x)")
    assert direct is not None
    assert "Equal logarithms, so equal arguments" in direct
    assert "Check $x = -5$" in direct and "x - 5 = -10 < 0" in direct
    assert "a logarithm needs a positive number" in direct
    assert "no real solution" in direct.split("**Answer**")[-1]


def test_a_square_root_on_the_other_side_restricts_its_radicand() -> None:
    """``\\sqrt{1 - x} \\ge 0`` is always true; the domain is ``1 - x \\ge 0``."""
    _, lhs, rhs = parse_equation(EquationInput(lhs="sqrt(x-3)", rhs="sqrt(1-x)"))
    steps = equation_key_steps(lhs, rhs, "x")
    assert steps[0].formula == r"x - 3 \ge 0 \quad\text{and}\quad 1 - x \ge 0"
    assert steps[-1].label == "Check $x = 2$"
    assert "x - 3 = -1 < 0" in steps[-1].formula


def test_a_log_trace_checks_the_root_it_rejects() -> None:
    _, lhs, rhs = parse_equation(EquationInput(lhs="log(x)+log(x+3)", rhs="log(4)"))
    labels = [step.label for step in equation_key_steps(lhs, rhs, "x")]
    assert labels[-2:] == ["Check $x = -4$", "Reject values outside the domain"]


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # An unread word that restricts the roots: no card (2026-11-14 review).
        ("Solve x^2 = 9 positive", None),
        ("Solve in N: x^2 = 4", None),
        ("solve x^2 = 9 integers only", None),
        # Read aloud, "negative x" is -x: the words still name a domain.
        ("solve x^2 - 4 = 0 for negative x", None),
        # Look-alikes: a signed number, and "n" as the unknown, not the naturals.
        ("solve x plus negative 3 equals 5", "x = 8"),
        ("solve x + 3 = -2", "x = -5"),
        ("solve n^2 = 16", r"n = \pm 4"),
    ],
)
async def test_a_bare_domain_word_beside_an_equation_takes_its_card(
    text: str, answer: str | None
) -> None:
    got, _direct = await _reply(text)
    assert got == answer
