"""Whole-request and metamorphic guarantees at the math extraction seam."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent


@pytest.mark.parametrize(
    "question, answer",
    [
        ("sin(30°) + cos(60°)", "1"),
        ("2sin(30°)+cos(60°)", r"\frac{3}{2}"),
        ("sin(pi/6)+cos(pi/3)", "1"),
        ("sin(π/6) + cos(π/3)", "1"),
        ("Evaluate sin(30°) + cos(60°)", "1"),
    ],
)
def test_complete_trig_expression_consumes_every_call(question: str, answer: str) -> None:
    intent = extract_math_intent(question)
    assert intent is not None and intent.school_op == "expression"
    block = _build_verified_block(intent, Settings())
    assert block is not None and block.canonical_answer == answer


@pytest.mark.parametrize(
    "question",
    [
        "sin(30°) + cos(60°) and calculate 99",
        "Simplify 8/12 and solve 2x=4",
        "Graph y=x^2 and solve 3x=9",
        "Find the mean and standard deviation of 1,2,3,4",
    ],
)
def test_unsupported_multipart_request_fails_closed(question: str) -> None:
    assert extract_math_intent(question) is None


def test_supported_geometry_multipart_retains_both_requested_values() -> None:
    question = "Find the area and perimeter of a rectangle 3 by 4"
    intent = extract_math_intent(question)
    assert intent is not None
    assert intent.wants_area is True
    assert intent.wants_perimeter is True
    block = _build_verified_block(intent, Settings())
    assert block is not None and block.canonical_fence is not None
    assert block.canonical_fence["area"] == 12
    assert block.canonical_fence["perimeter"] == 14
    assert maybe_direct_math_reply(block, question) is None


def test_named_rectangle_multipart_is_verified_and_rendered_atomically() -> None:
    question = "A rectangle is 8 cm long and 3 cm wide. Find both its area and perimeter."
    intent = extract_math_intent(question)
    assert intent is not None
    assert intent.wants_area is True and intent.wants_perimeter is True
    block = _build_verified_block(intent, Settings())
    assert block is not None
    assert block.canonical_answer == (r"A = 24\ \mathrm{cm}^{2},\quad P = 22\ \mathrm{cm}")
    reply = maybe_direct_math_reply(block, question)
    assert reply is not None
    assert "A = 8 \\times 3 = 24" in reply
    assert "P = 2(8+3) = 22" in reply


@pytest.mark.parametrize(
    "question",
    [
        "solve 2x+3=11",
        "solve: 2x + 3 = 11",
        "please solve 2x+3=11",
        "show me how to solve 2x+3=11",
        "Solve 2x + 3 = 11.",
    ],
)
def test_equivalent_wrappers_preserve_the_same_equation(question: str) -> None:
    intent = extract_math_intent(question)
    assert intent is not None and intent.kind == "equation"
    assert (intent.lhs or "").replace(" ", "") == "2x+3"
    assert intent.rhs == "11"


def test_zero_exponent_law_is_part_of_verified_working() -> None:
    question = "Show steps: 3x^2 + x^0 = 3"
    intent = extract_math_intent(question)
    assert intent is not None
    block = _build_verified_block(intent, Settings())
    assert block is not None
    assert block.key_steps[0].label == "Use the zero-exponent law"
    assert block.key_steps[0].formula == "x^0 = 1"
    assert block.key_steps[0].conditions == r"x \ne 0"
    reply = maybe_direct_math_reply(block, question)
    assert reply is not None and "zero-exponent law" in reply.lower()
