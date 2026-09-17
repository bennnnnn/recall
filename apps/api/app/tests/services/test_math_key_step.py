"""Verified equation lessons from structured ``key_steps``.

``solve x^2 - 5x + 6 = 0`` used to return a bare chip (or a one-line
factorization). The working is now a server-rendered Given / one-transformation
trace so it cannot drift from the chip. SHORT and “just the answer” stay a chip.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import solve as math_solve
from app.services.math.tools import (
    _build_verified_block,
    extract_math_intent,
    maybe_direct_math_reply,
    wants_math_explanation,
)


def _block(text: str):
    intent = extract_math_intent(text)
    assert intent is not None, f"no intent for {text!r}"
    return _build_verified_block(intent, Settings(math_tools_enabled=True))


@pytest.mark.parametrize(
    "lhs, rhs, expected",
    [
        ("x^2 - 5x + 6", "0", "\\left(x - 3\\right) \\left(x - 2\\right)"),
        ("x^2 - 9", "0", "\\left(x - 3\\right) \\left(x + 3\\right)"),
        ("x^2 + 2x + 1", "0", "\\left(x + 1\\right)^{2}"),
    ],
)
def test_factored_key_step_returns_the_factorization(lhs: str, rhs: str, expected: str) -> None:
    assert math_solve.factored_key_step(lhs, rhs) == expected


@pytest.mark.parametrize(
    "lhs, rhs",
    [
        ("2x + 7", "19"),
        ("x^2 + 1", "0"),
        ("x^2 + x + 1", "0"),
    ],
)
def test_factored_key_step_stays_quiet_when_factoring_is_not_the_step(lhs: str, rhs: str) -> None:
    assert math_solve.factored_key_step(lhs, rhs) is None


def test_show_steps_phrase_is_an_explanation_request() -> None:
    assert wants_math_explanation("Show steps: 2x + 3 = 11") is True
    assert wants_math_explanation("Hint only: x^2 + 2 = 6") is False


def test_seven_times_eight_is_a_bare_chip() -> None:
    text = "7*8"
    for style in ("short", "balanced", "detailed"):
        reply = maybe_direct_math_reply(_block(text), text, response_style=style)
        assert reply is not None
        assert reply.startswith("```answer")
        assert "56" in reply
        assert "Given" not in reply


def test_show_steps_linear_lesson_overrides_short() -> None:
    text = "Show steps: 2x + 3 = 11"
    reply = maybe_direct_math_reply(_block(text), text, response_style="short")

    assert reply is not None
    assert "**Given:**" in reply
    assert "Subtract 3 from both sides" in reply
    assert "Divide both sides by 2" in reply
    assert reply.index("Subtract") < reply.index("Divide")
    assert "```answer" in reply
    assert "x = 4" in reply
    # Label and formula are on separate lines; chip is last.
    subtract_line = next(line for line in reply.splitlines() if line.startswith("1."))
    assert "$" not in subtract_line
    assert reply.strip().endswith("```") or "```answer" in reply.split("Check:")[0]


def test_one_op_linear_stays_a_chip_on_balanced() -> None:
    text = "x+7=12"
    reply = maybe_direct_math_reply(_block(text), text, response_style="balanced")

    assert reply is not None
    assert "Given" not in reply
    assert reply.startswith("```answer")
    assert "x = 5" in reply


def test_balanced_two_op_linear_is_a_lesson() -> None:
    text = "2x + 7 = 19"
    reply = maybe_direct_math_reply(_block(text), text, response_style="balanced")

    assert reply is not None
    assert "Subtract 7 from both sides" in reply
    assert "Divide both sides by 2" in reply
    assert reply.index("Subtract") < reply.index("Divide")
    assert "```answer" in reply
    assert "x = 6" in reply
    # Final simplification lives in the chip, not a second copy above it.
    before_chip, _, after = reply.partition("```answer")
    assert before_chip.count("x = 6") == 0


def test_detailed_pure_power_uses_absolute_value() -> None:
    text = "x^2 + 2 = 6"
    reply = maybe_direct_math_reply(_block(text), text, response_style="detailed")

    assert reply is not None
    assert "**Given:**" in reply
    assert "Take square roots of both sides" in reply
    assert r"\lvert" in reply or r"\left|" in reply
    assert "```answer" in reply
    assert r"\pm 2" in reply
    assert "Check:" in reply


def test_just_the_answer_keeps_the_chip_on_detailed() -> None:
    text = "Just the answer: x^2 + 2 = 6"
    reply = maybe_direct_math_reply(_block(text), text, response_style="detailed")

    assert reply is not None
    assert "Given" not in reply
    assert reply.startswith("```answer")
    assert r"\pm 2" in reply


def test_balanced_factorable_quadratic_is_a_factor_trace() -> None:
    text = "solve x^2 - 5x + 6 = 0"
    reply = maybe_direct_math_reply(_block(text), text, response_style="balanced")

    assert reply is not None
    assert "Factor the left side" in reply
    assert "Factors as" not in reply
    assert "x - 2" in reply and "x - 3" in reply
    assert "```answer" in reply
    assert "quadratic formula" in reply.lower()


def test_short_keeps_the_bare_answer() -> None:
    text = "solve x^2 - 5x + 6 = 0"
    reply = maybe_direct_math_reply(_block(text), text, response_style="short")

    assert reply is not None
    assert "Factor the left side" not in reply
    assert "Factors as" not in reply
    assert reply.startswith("```answer")


def test_detailed_irreducible_quadratic_uses_the_formula() -> None:
    text = "solve x^2 - 2x - 1 = 0"
    reply = maybe_direct_math_reply(_block(text), text, response_style="detailed")

    assert reply is not None
    assert "Quadratic formula" in reply
    assert r"\pm" in reply
    assert r"\sqrt{2}" in reply or r"\sqrt{2}" in reply.replace(" ", "")
    assert "1" in reply
    assert "```answer" in reply


def test_joke_request_still_keeps_the_model() -> None:
    text = "solve 2x + 3 = 11 and tell me a joke"
    assert maybe_direct_math_reply(_block(text), text, response_style="balanced") is None


def test_default_style_is_balanced() -> None:
    text = "solve x^2 - 5x + 6 = 0"
    assert maybe_direct_math_reply(_block(text), text) == maybe_direct_math_reply(
        _block(text), text, response_style="balanced"
    )
