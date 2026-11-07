"""A matrix question that lists several results gets every one, worked, on one card.

2026-11-06: "find the determinant and inverse of [[2,1],[5,3]]" was read as the
determinant alone; the model's Inverse section ended on ``\\det(A) = 1`` and the
card held ``1``.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.match.matrix_requests import requested_matrix_ops, without_matrix_cues
from app.modules.math.tools.extract import extract_math_intent
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply


async def _reply(text: str) -> tuple[str | None, str | None]:
    """(canonical answer, direct reply) for one turn, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    augmentation = await build_subject_augmentation(text, settings)
    verified = augmentation.verified
    answer = getattr(verified, "canonical_answer", None) if verified is not None else None
    return answer, maybe_direct_subject_reply(verified, text)


@pytest.mark.parametrize(
    ("text", "ops"),
    [
        ("find the determinant and inverse of [[2,1],[5,3]]", ("determinant", "inverse")),
        ("inverse and determinant of [[2,1],[5,3]]", ("inverse", "determinant")),
        ("what are the rank and the transpose of [[1,2],[3,4]]", ("rank", "transpose")),
        ("eigenvalues and eigenvectors of [[2,1],[1,2]]", ("eigenvalues", "eigenvectors")),
        ("det, rank and rref of [[1,2],[2,4]]", ("determinant", "rank", "rref")),
        ("the determinant of [[2,1],[5,3]] and its inverse", ("determinant", "inverse")),
        # One operation, two matrices, or an operation between two: one result.
        ("determinant of [[2,1],[5,3]]", ()),
        ("multiply [[1,2],[3,4]] and [[0,1],[1,0]]", ()),
        ("A = [[1,2],[3,4]] times its inverse", ()),
    ],
)
def test_requested_matrix_ops_lists_each_result_in_order(text: str, ops: tuple[str, ...]) -> None:
    assert requested_matrix_ops(text) == ops


@pytest.mark.parametrize(
    "text",
    [
        "find the inverse of the transpose of [[2,1],[5,3]]",
        "the determinant of the inverse of [[2,1],[5,3]]",
        "rank of the transpose of [[1,2],[3,4]]",
    ],
)
def test_one_operation_of_another_is_a_composition_and_declines(text: str) -> None:
    assert requested_matrix_ops(text) is None
    assert extract_math_intent(text) is None


def test_without_matrix_cues_leaves_only_the_glue() -> None:
    text = "find the determinant and inverse of [[2,1],[5,3]] and tell me a joke"
    assert without_matrix_cues(text) == "find the and of and tell me a joke"


def test_the_extractor_reads_every_listed_result() -> None:
    intent = extract_math_intent("find the determinant and inverse of [[2,1],[5,3]]")
    assert intent is not None
    assert intent.kind == "matrix"
    assert intent.matrix_op == "determinant"
    assert intent.matrix_ops == ["determinant", "inverse"]


@pytest.mark.asyncio
async def test_determinant_and_inverse_are_both_worked_and_both_on_the_card() -> None:
    answer, reply = await _reply("find the determinant and inverse of [[2,1],[5,3]]")
    inverse = r"\left[\begin{matrix}3 & -1\\-5 & 2\end{matrix}\right]"
    assert answer == rf"\det(A) = 1,\quad A^{{-1}} = {inverse}"
    assert reply is not None
    # The reply writes products the school way, with \times.
    assert r"\det(A) = 2 \times 3 - 1 \times 5 = 1$ — $ad - bc$" in reply
    assert r"\operatorname{adj}(A)" in reply
    assert reply.rstrip().endswith(f"```answer\n{answer}\n```")


@pytest.mark.asyncio
async def test_a_three_by_three_determinant_expands_along_the_first_row() -> None:
    answer, reply = await _reply("determinant and inverse of [[1,-2,3],[0,1,4],[5,6,0]]")
    assert answer is not None and answer.startswith(r"\det(A) = -79,\quad A^{-1} = ")
    assert reply is not None
    assert "expand along the first row" in reply
    assert r"\frac{1}{-79}" in reply


@pytest.mark.asyncio
async def test_a_singular_matrix_gives_its_determinant_and_says_there_is_no_inverse() -> None:
    answer, reply = await _reply("find the determinant and inverse of [[2,4],[1,2]]")
    assert answer == r"\det(A) = 0,\quad A^{-1}\ \text{does not exist}"
    assert reply is not None and "has no inverse" in reply


@pytest.mark.asyncio
async def test_rank_and_transpose_of_a_rectangular_matrix() -> None:
    answer, _ = await _reply("what are the rank and the transpose of [[1,2,3],[4,5,6]]")
    assert answer == (
        r"\operatorname{rank}(A) = 2,\quad "
        r"A^{T} = \left[\begin{matrix}1 & 4\\2 & 5\\3 & 6\end{matrix}\right]"
    )


@pytest.mark.asyncio
async def test_another_request_beside_the_results_keeps_the_model_with_both_verified() -> None:
    text = "find the determinant and inverse of [[2,1],[5,3]] and tell me a joke"
    answer, reply = await _reply(text)
    assert answer is not None and r"A^{-1} = " in answer and r"\det(A) = 1" in answer
    assert reply is None


@pytest.mark.asyncio
async def test_one_result_keeps_its_single_card() -> None:
    answer, _ = await _reply("inverse of [[4,7],[2,6]]")
    assert answer is not None and not answer.startswith("A^{-1}")
