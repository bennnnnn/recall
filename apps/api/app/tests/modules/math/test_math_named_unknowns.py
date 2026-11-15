"""A subscripted name, or a letter of another alphabet, is never read as part of itself.

The equation walker steps out from ``=`` over the characters a side may hold, and it carries
no ``_``, lowered digit or Greek letter. Stopped there, a side was the tail of a name: "a_n =
2n" was n = 2n, a checked n = 0; "Find the sum of the first n terms of aₙ = 2n + 1" a checked
n = -1; "x₁ + x₂ = 5" was 2 = 5, a checked "no solution"; "5 = x_1 + 2" was 5 = x; and "2θ +
1 = 7" was + 1 = 7 (2026-11-14). A side cut short inside a name is no side, so the turn goes to
the model unchecked, and a sequence's rule is never solved for its index.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.solve import (
    try_extract_compound_inequality_from_text,
    try_extract_equations_from_text,
    try_extract_inequality_from_text,
)
from app.services.subjects.dispatch import build_subject_augmentation


async def _verified(text: str) -> str | None:
    """The turn's checked answer, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.parametrize(
    "text",
    [
        "a_n = 2n",
        "Find the sum of the first n terms of a_n = 2n + 1",
        "u_{n+1} = 2u_n",
        "x_1 + x_2 = 5",
        "5 = x_1 + 2",
        "x + a_1 = 3",
        "2x_1 = 6",
        "log_2 x = 5",
        "2θ + 1 = 7",
        "3 = 2α",
    ],
)
def test_a_side_cut_inside_a_name_is_no_equation(text: str) -> None:
    assert try_extract_equations_from_text(text) == []


@pytest.mark.parametrize("text", ["x_1 + 2 > 5", "2 < a_n", "2θ > 6"])
def test_a_side_cut_inside_a_name_is_no_inequality(text: str) -> None:
    assert try_extract_inequality_from_text(text) is None


def test_a_compound_inequality_cut_inside_a_name_is_none() -> None:
    assert try_extract_compound_inequality_from_text("1 < x_1 < 5") is None


@pytest.mark.parametrize(
    ("text", "pairs"),
    [
        ("2x + 3 = 7", [("2x + 3", "7")]),
        ("x + y = 5, x - y = 1", [("x + y", "5"), ("x - y", "1")]),
        # A name before a space, or prose of any alphabet around it, cuts nothing.
        ("let a_1 be the start and 2x + 3 = 7", [("2x + 3", "7")]),
        ("2x + 3 = 7 años", [("2x + 3", "7")]),
    ],
)
def test_an_equation_beside_a_name_is_still_read(text: str, pairs: list[tuple[str, str]]) -> None:
    assert try_extract_equations_from_text(text) == pairs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Find the sum of the first n terms of aₙ = 2n + 1",
        "Find the sum of the first n terms of a_n = 2n",
        "If bₙ = 3n, find n",
        "Solve a_n = 2n",
        "u_{n+1} = 2u_n, find n",
        "Solve x₁ + x₂ = 5",
        "Solve x_1 + x_2 = 5",
        "5 = x_1 + 2",
        "Solve 2x_1 = 6",
        "Solve x_1 + x_2 = 5, x_1 - x_2 = 1",
        "Solve x_1 + 2 > 5",
        "Solve 2θ + 1 = 7",
    ],
)
async def test_an_equation_in_a_subscripted_name_gets_no_card(question: str) -> None:
    assert await _verified(question) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Solve 2x + 3 = 7", "x = 2"),
        ("Solve x + y = 5, x - y = 1", "x = 3, y = 2"),
        ("Solve log_2(x) = 3", "x = 8"),
        ("Résous 2x + 3 = 7", "x = 2"),
    ],
)
async def test_an_equation_with_no_name_in_it_is_still_solved(question: str, answer: str) -> None:
    assert await _verified(question) == answer
