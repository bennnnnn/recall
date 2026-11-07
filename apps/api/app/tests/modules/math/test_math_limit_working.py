"""A 0/0 limit shows its working, however many rounds of L'Hôpital's rule it takes.

2026-11-06: "the limit of (1-cos x)/x^2 as x goes to 0" was a bare ``1/2`` card: one
round gives ``sin x / 2x``, still 0/0, and the working stopped there.
"""

from __future__ import annotations

import pytest
from sympy import Symbol, cos, exp, sin

from app.core.config import Settings
from app.modules.math.tools.block.limits import _lhopital_rows
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply


async def _reply(text: str) -> tuple[str | None, str | None]:
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    augmentation = await build_subject_augmentation(text, settings)
    verified = augmentation.verified
    answer = getattr(verified, "canonical_answer", None) if verified is not None else None
    return answer, maybe_direct_subject_reply(verified, text)


x = Symbol("x", real=True)


@pytest.mark.parametrize(
    ("top", "bottom", "value", "rounds"),
    [
        (sin(x), x, 1, 1),
        (1 - cos(x), x**2, 0.5, 2),
        (exp(x) - 1 - x, x**2, 0.5, 2),
        (x - sin(x), x**3, 1 / 6, 3),
    ],
)
def test_lhopital_rows_take_as_many_rounds_as_the_limit_needs(
    top: object, bottom: object, value: float, rounds: int
) -> None:
    from sympy import nsimplify

    rows = _lhopital_rows(top, bottom, x, 0, nsimplify(value))
    assert rows is not None
    assert len(rows) == rounds


def test_a_wrong_value_is_never_worked_towards() -> None:
    assert _lhopital_rows(1 - cos(x), x**2, x, 0, 1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer", "lines"),
    [
        (
            "what is the limit of (1-cos x)/x^2 as x goes to 0",
            r"\frac{1}{2}",
            [
                r"\lim_{x \to 0} \frac{\sin{\left(x \right)}}{2 x}",
                r"$= \lim_{x \to 0} \frac{\cos{\left(x \right)}}{2}$ — $\frac{0}{0}$ again",
                r"$= \frac{1}{2}$ — substitute $x = 0$",
            ],
        ),
        (
            "lim x->0 (x - sin x)/x^3",
            r"\frac{1}{6}",
            [r"\lim_{x \to 0} \frac{\cos{\left(x \right)}}{6}", "L'Hôpital's rule"],
        ),
        (
            "limit as x approaches 2 of (x^2-4)/(x-2)",
            "4",
            ["factor and cancel", r"\lim_{x \to 2} \left(x + 2\right) = 4"],
        ),
    ],
)
async def test_the_limit_reply_shows_each_step(text: str, answer: str, lines: list[str]) -> None:
    got, reply = await _reply(text)
    assert got == answer
    assert reply is not None
    for line in lines:
        assert line in reply


@pytest.mark.asyncio
async def test_a_limit_with_another_request_keeps_the_model() -> None:
    _, reply = await _reply("limit as x approaches 2 of (x^2-4)/(x-2) and tell me a joke")
    assert reply is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("limit of 1/x - 1/sin(x) as x approaches 0", "0"),
        ("limit of (1/x - 1/(exp(x)-1)) as x approaches 0", r"\frac{1}{2}"),
    ],
)
async def test_infinity_minus_infinity_is_not_worked_as_zero_over_zero(
    text: str, answer: str
) -> None:
    got, reply = await _reply(text)
    assert got == answer
    # No working of its own, so no server reply: the model writes the method around the
    # checked card (main's rule since #2311), and the server never works it as 0/0.
    assert reply is None


def test_a_failing_limit_loses_the_working_not_the_turn() -> None:
    from unittest.mock import patch

    with patch("sympy.limit", side_effect=NotImplementedError("no limit")):
        assert _lhopital_rows(sin(x), x, x, 0, 1) is None
