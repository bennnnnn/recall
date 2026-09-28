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
        "Find the mean and median of 1,2,3,4",
        "Find the median and mode of 1,1,2,3",
        "Find median of 1,2,3 and z-score for x=88, mean 72, standard deviation 8",
        "Solve 2x=4; also x must be positive",
        "Solve x²=4 for x > 0",
        "Differentiate x² and evaluate it at x=3",
        "Find the derivative and second derivative of x³",
        "Graph x² and tell me its roots",
        "Find the area, perimeter and diagonal of a 3×4 rectangle",
        "Find sin(30°), cos(60°), and tan(45°)",
        "Solve x²=4 in the integers",
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


def test_z_score_input_labels_are_not_mistaken_for_requested_statistics() -> None:
    question = (
        "Find the z-score for x=88 where the population mean is 72 and standard deviation is 8"
    )
    intent = extract_math_intent(question)
    assert intent is not None
    assert intent.school_op == "z_score"
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.direct_reply is not None
    assert r"\frac{88 - 72}{8} = 2" in block.direct_reply


def test_square_root_in_graph_expression_is_not_a_roots_request() -> None:
    intent = extract_math_intent("Graph the square root of x")
    assert intent is not None
    assert intent.kind == "graph"


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
