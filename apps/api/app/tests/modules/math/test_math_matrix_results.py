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
        ("determinant of [[2,1],[5,3]]", ("determinant",)),
        ("find the determinant of this matrix [[2,1],[5,3]]", ("determinant",)),
        # An operation named as the method is no result.
        ("find the inverse of [[2,1],[5,3]] without computing the determinant", ("inverse",)),
        ("use the determinant to find the inverse of [[2,1],[5,3]]", ("inverse",)),
        # Two matrices: the single-operation reader owns them.
        ("multiply [[1,2],[3,4]] and [[0,1],[1,0]]", ()),
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
        # 2026-11-06 review: each was answered about A.
        "find the inverse of [[2,1],[5,4]] and the determinant of the inverse",
        "find the inverse of [[2,1],[5,4]] and the eigenvalues of the inverse",
        "the eigenvalues of [[2,0],[0,3]] and of its inverse",
        "find the transpose of [[2,1],[5,3]] and then the inverse of that",
        "find the determinant of [[2,1],[5,3]] and of its transpose",
        "A = [[1,2],[3,4]] times its inverse",
        "[[1,2],[3,4]] * its inverse",
        # One matrix in arithmetic: the results are 2A's.
        "determinant and rank of [[1,2],[3,4]] times 2",
        "det 2[[1,2],[3,4]]",
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "find the inverse of [[2,1],[5,3]] without computing the determinant",
        "use the determinant to find the inverse of [[2,1],[5,3]]",
    ],
)
async def test_an_operation_named_as_the_method_is_not_on_the_card(text: str) -> None:
    answer, _ = await _reply(text)
    assert answer == r"\left[\begin{matrix}3 & -1\\-5 & 2\end{matrix}\right]"


@pytest.mark.asyncio
async def test_every_card_result_says_whose_it_is() -> None:
    answer, _ = await _reply("find the eigenvalues and eigenvectors of [[2,1],[1,2]]")
    assert answer is not None
    assert answer.startswith(r"\lambda(A) = 1, 3,\quad E_{1}(A) = \operatorname{span}")
    assert r",\quad E_{3}(A) = \operatorname{span}" in answer
    assert r"\lambda=" not in answer


@pytest.mark.parametrize(
    ("typed", "read"),
    [
        ("[[2, 1], [5, 3]]", "[[2,1],[5,3]]"),
        ("[ [2, 1] , [5, 3] ]", "[[2,1],[5,3]]"),
        ("[[2 1], [5 3]]", "[[2,1],[5,3]]"),
        ("[[2 1] [5 3]]", "[[2,1],[5,3]]"),
        ("[[1, 2, 3],\n [4, 5, 6],\n [7, 8, 10]]", "[[1,2,3],[4,5,6],[7,8,10]]"),
        ("[[-1.5, .5], [2, -3]]", "[[-1.5,.5],[2,-3]]"),
        # Not a matrix of numbers apart by spaces: left for its reader to decline.
        ("[[2 - 1], [5, 3]]", "[[2 - 1],[5,3]]"),
        ("a list [1, 2, 3]", "a list [1, 2, 3]"),
        ("see [1] and [2]", "see [1] and [2]"),
    ],
)
def test_a_matrix_reads_the_same_however_it_is_spaced(typed: str, read: str) -> None:
    from app.modules.math.match.scan import fold_matrix_spacing

    assert fold_matrix_spacing(typed) == read


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("find the determinant of [[2, 1], [5, 3]]", "1"),
        ("find the determinant of [[2,1],[5,3]]", "1"),
        ("det [[2 3], [1 4]]", "5"),
        ("find the determinant and inverse of [ [2, 1] , [5, 3] ]", r"\det(A) = 1"),
    ],
)
async def test_a_spaced_matrix_is_worked_like_an_unspaced_one(text: str, answer: str) -> None:
    """MATH-07 (2026-11-13 audit): "[[2, 1], [5, 3]]" was not maths at all."""
    got, _direct = await _reply(text)
    assert got is not None and got.startswith(answer)
