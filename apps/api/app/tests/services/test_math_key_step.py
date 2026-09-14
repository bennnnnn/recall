"""The one line of working a person would have given the first time.

`solve x^2 - 5x + 6 = 0` returned a bare `x = 2 or x = 3` on the direct path,
so seeing where it came from cost a second turn ("how?"). The factorization is
computed here rather than by the model, so it stays verified and adds no
latency. SHORT asked for less; DETAILED asked for more than this path can give.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import solve as math_solve
from app.services.math.tools import (
    _build_verified_block,
    extract_math_intent,
    maybe_direct_math_reply,
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
        ("2x + 7", "19"),  # linear — one operation, nothing worth showing
        ("x^2 + 1", "0"),  # irreducible over the rationals
        ("x^2 + x + 1", "0"),
    ],
)
def test_factored_key_step_stays_quiet_when_there_is_no_step(lhs: str, rhs: str) -> None:
    assert math_solve.factored_key_step(lhs, rhs) is None


def test_balanced_shows_the_factorization_without_being_asked() -> None:
    text = "solve x^2 - 5x + 6 = 0"
    reply = maybe_direct_math_reply(_block(text), text, response_style="balanced")

    assert reply is not None
    assert reply.startswith("Factors as $")
    assert "x - 2" in reply and "x - 3" in reply
    assert "```answer" in reply


def test_short_keeps_the_bare_answer() -> None:
    text = "solve x^2 - 5x + 6 = 0"
    reply = maybe_direct_math_reply(_block(text), text, response_style="short")

    assert reply is not None
    assert "Factors as" not in reply
    assert reply.startswith("```answer")


def test_detailed_hands_the_turn_to_the_model_for_real_working() -> None:
    text = "solve x^2 - 5x + 6 = 0"
    assert maybe_direct_math_reply(_block(text), text, response_style="detailed") is None


@pytest.mark.parametrize("text", ["solve 2x + 7 = 19", "what is 2+2"])
def test_one_step_problems_stay_bare_in_every_style(text: str) -> None:
    """A smart person does not explain 2 + 2. Only DETAILED changes the path."""
    block = _block(text)
    for style in ("short", "balanced"):
        reply = maybe_direct_math_reply(block, text, response_style=style)
        assert reply is not None
        assert "Factors as" not in reply


def test_default_style_is_balanced() -> None:
    """Callers that predate the parameter get the key step, not the bare answer."""
    text = "solve x^2 - 5x + 6 = 0"
    assert maybe_direct_math_reply(_block(text), text) == maybe_direct_math_reply(
        _block(text), text, response_style="balanced"
    )
