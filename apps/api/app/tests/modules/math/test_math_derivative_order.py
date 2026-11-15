"""A derivative question is answered at the order it names, or not at all.

The order reader knew "second", "third" and their digits and read every other order as the
first: "Find the 4th derivative of x^5" was a checked 5x⁴, "the nth derivative of e^(2x)" a
checked 2e^(2x), and with raised suffixes "the 2ⁿᵈ derivative of eˣsin x" and "the 3ʳᵈ
derivative of sin x" came back as first derivatives too (2026-11-14). The tool check took a
first derivative for any question, whatever order it asked. "The eleventh", "the 1000th",
"the 5-th" and "the 3 rd" were still read as no ordinal, so as the first (review, 2026-11-15).
"""

from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.modules.math.match.derivative_order import asked_derivative_order, derivative_orders
from app.modules.math.tool_check import tool_call_matches_user_text
from app.services.subjects.dispatch import build_subject_augmentation


async def _verified(text: str) -> str | None:
    """The turn's checked answer, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.parametrize(
    ("text", "order"),
    [
        ("find the derivative of x^4", 1),
        ("find the first derivative of x^4", 1),
        ("find the 2nd derivative of x^4", 2),
        ("find the second derivative of x^4", 2),
        ("the 3rd derivative of sin x", 3),
        ("the 4th derivative of x^5", 4),
        ("the fourth-order derivative of x^5", 4),
        ("the 5th derivative of x^6", 5),
        ("find d^2y/dx^2 if y = x^4", 2),
        ("find d^2/dx^2 of x^4", 2),
        ("find f''(x) if f(x) = x^4", 2),
        ("find f''''(x) if f(x) = x^5", 4),
        # The second derivative, wherever f'(x) is mentioned beside it.
        ("find the second derivative given f'(x) = 3x^2", 2),
        # An order no number gives.
        ("find the nth derivative of e^(2x)", None),
        ("find the kth derivative of sin x", None),
        ("find the n-th derivative of x^n", None),
        ("find the (n+1)th derivative of x^n", None),
        ("find d^(n)y/dx^(n) if y = e^x", None),
        # Every ordinal before "derivative", spelled or in digits, apart from its suffix or not.
        ("find the eleventh derivative of x^12", 11),
        ("find the twentieth derivative of x^20", 20),
        ("find the twenty-first derivative of x^21", 21),
        ("find the 1000th derivative of sin x", 1000),
        ("find the 5-th derivative of x^6", 5),
        ("find the 3 rd derivative of x^5", 3),
        ("find the 2 nd derivative of x^5", 2),
        ("find the 2nd-order derivative of x^4", 2),
        ("find the second partial derivative of x^2 y", 2),
        # Shaped like an ordinal and read as none: no number gives it here.
        ("find the hundred and first derivative of x^5", None),
        ("find the zeroth derivative of x^5", None),
        ("find the umpteenth derivative of x^5", None),
        # Not an order: a power of the letter d, a sentence's "first", a 2nd elsewhere.
        ("differentiate d^2 + 3d", 1),
        ("first, find the derivative of x^3", 1),
        ("my 2nd attempt: the derivative of x^3", 1),
        ("find both partial derivatives of x^2 y", 1),
        ("find the antiderivative of x^3", 1),
    ],
)
def test_the_order_a_question_names(text: str, order: int | None) -> None:
    assert asked_derivative_order(text) == order


def test_every_order_named_is_read() -> None:
    assert derivative_orders("the first and second derivatives of x^3") == (1, 2)
    assert derivative_orders("the first, second and third derivatives of x^3") == (1, 2, 3)
    assert derivative_orders("the first, second, and third derivatives of x^3") == (1, 2, 3)
    assert derivative_orders("the first or 2nd derivative of x^3") == (1, 2)
    assert derivative_orders("the derivative of x^3") == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "plain"),
    [
        ("Find the 2ⁿᵈ derivative of x⁴", "Find the second derivative of x^4"),
        ("Find the 3ʳᵈ derivative of sin x", "Find the third derivative of sin x"),
        ("What is the 2ⁿᵈ derivative of 5x³?", "What is the second derivative of 5x^3?"),
        ("Find the 2ⁿᵈ derivative of eˣsin x", "Find the second derivative of e^x sin x"),
        ("Find the 2ⁿᵈ derivative of x³ at x = 1", "Find the second derivative of x^3 at x = 1"),
        ("Find the 4ᵗʰ derivative of x⁵", "Find the fourth derivative of x^5"),
    ],
)
async def test_a_raised_ordinal_is_the_order_it_writes(typed: str, plain: str) -> None:
    expected = await _verified(plain)
    assert expected is not None, plain
    assert await _verified(typed) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Find the 2ⁿᵈ derivative of x⁴", "12 x^{2}"),
        ("Find the 3ʳᵈ derivative of sin x", r"- \cos{\left(x \right)}"),
        ("What is the 2ⁿᵈ derivative of 5x³?", "30 x"),
        ("Find the 2ⁿᵈ derivative of x³ at x = 1", "6"),
        ("Find the 4th derivative of x^5", "120 x"),
        ("Find the fourth derivative of x^5", "120 x"),
        ("Find the 3 rd derivative of x^5", "60 x^{2}"),
        ("Find the 2 nd derivative of x^5", "20 x^{3}"),
        # Unchanged: the first, and an order already read.
        ("Find the derivative of x^4", "4 x^{3}"),
        ("Find the second derivative of x^4", "12 x^{2}"),
        ("Differentiate d^2 + 3d", "2 d + 3"),
    ],
)
async def test_a_derivative_is_worked_at_its_order(question: str, answer: str) -> None:
    assert await _verified(question) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Find the nᵗʰ derivative of e²ˣ",
        "Find the nth derivative of e^(2x)",
        "Find the kth derivative of sin x",
        "Find the (n+1)th derivative of x^n",
        # Past the highest order the solver works: never the first in its place.
        "Find the 5th derivative of x^6",
        "Find the eleventh derivative of x^12",
        "Find the 1000th derivative of sin x",
        "Find the 5-th derivative of x^6",
        "Find the hundred and first derivative of x^5",
    ],
)
async def test_an_order_no_number_gives_is_declined(question: str) -> None:
    assert await _verified(question) is None


@pytest.mark.parametrize(
    ("order", "user", "matches"),
    [
        (1, "find the derivative of x^4", True),
        (2, "find the derivative of x^4", False),
        (2, "find the 2nd derivative of x^4", True),
        (1, "find the 2nd derivative of x^4", False),
        (2, "find the 2ⁿᵈ derivative of x⁴", True),
        (1, "find the 2ⁿᵈ derivative of x⁴", False),
        (4, "find the 4th derivative of x^4", True),
        (1, "find the nth derivative of x^4", False),
        (1, "the first and second derivatives of x^4", True),
        (2, "the first and second derivatives of x^4", True),
        (1, "find the eleventh derivative of x^4", False),
        (1, "find the 1000th derivative of x^4", False),
        (3, "find the 3 rd derivative of x^4", True),
        (1, "find the 3 rd derivative of x^4", False),
    ],
)
def test_a_tool_call_is_held_to_the_order_asked(order: int, user: str, matches: bool) -> None:
    args = json.dumps({"action": "diff", "expr": "x**4", "variable": "x", "order": order})
    assert tool_call_matches_user_text(args, [user]) is matches
