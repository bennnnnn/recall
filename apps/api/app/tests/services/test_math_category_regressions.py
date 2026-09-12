"""Representative extraction-to-answer checks, without external IO."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services import math_tools


@pytest.mark.parametrize(
    "text,kind,answer",
    [
        ("7*8", "arithmetic", "56"),
        ("8-8*2", "arithmetic", "-8"),
        ("what is 9/9", "arithmetic", "1"),
        ("15% of 80", "arithmetic", "12"),
        (r"\sqrt[6]{9}", "arithmetic", r"\sqrt[3]{3}"),
        (r"sqrt[6]{9}", "arithmetic", r"\sqrt[3]{3}"),
        (r"\sqrt{\sqrt{16}}", "arithmetic", "2"),
        (r"2/\frac{1}{2}", "arithmetic", "4"),
        (r"\frac{2}{3}^2", "arithmetic", r"\frac{4}{9}"),
        (r"$\sqrt[6]{9}$", "arithmetic", r"\sqrt[3]{3}"),
        (r"9^{1/6}", "arithmetic", r"\sqrt[3]{3}"),
        (r"what is $9^{1/6}$?", "arithmetic", r"\sqrt[3]{3}"),
        (r"what is \sqrt{81}", "arithmetic", "9"),
        ("Let x=-5. Evaluate x^2", "arithmetic", "25"),
        ("Let x=-5. Evaluate 2*x^2", "arithmetic", "50"),
        ("Let x=5. Evaluate 2x", "arithmetic", "10"),
        ("simplify ratio 1.5:2.5", "arithmetic", "3:5"),
        ("simplify ratio 0.5:0.75", "arithmetic", "2:3"),
        ("solve 2x+3=7", "equation", "x = 2"),
        ("solve x^2=9", "equation", r"x = \pm 3"),
        ("solve x+y=5; x-y=1", "system", "x = 3, y = 2"),
        ("differentiate x^3", "calculus", "3 x^{2}"),
        ("differentiate y^3 with respect to y", "calculus", "3 y^{2}"),
        ("differentiate y^3 wrt y", "calculus", "3 y^{2}"),
        ("differentiate y^3 with respect to x", "calculus", "0"),
        ("d/dt t^3", "calculus", "3 t^{2}"),
        ("integrate y^2 dy", "calculus", r"\frac{y^{3}}{3} + C"),
        ("integrate t^2 dt from 0 to 2", "calculus", r"\frac{8}{3}"),
        ("integrate x^2 from 0 to 1", "calculus", r"\frac{1}{3}"),
        ("limit of sin(x)/x as x approaches 0", "limit", "1"),
        ("sum 1/n^2 from n=1 to infinity", "series", r"\frac{\pi^{2}}{6}"),
        ("area of rectangle 3 by 4", "rectangle", "12"),
        ("area of triangle base 3 height 4", "triangle", "6"),
        ("mean of 1,2,3,4", "statistics", "2.5"),
        ("mean of 1/2,3/2", "statistics", "1"),
        ("mean of 1e3,3e3", "statistics", "2000"),
        ("sample variance of 1,2,3", "statistics", "1"),
        ("population variance of 1,2,3", "statistics", "0.666667"),
        ("binomial n=5 k=2 p=0.5", "probability", "0.3125"),
        ("binomial p=1/2 k=2 n=5", "probability", "0.3125"),
        ("expected value of 1,2,3", "probability", "2"),
        ("expected value of 1/2,3/2", "probability", "1"),
        ("5 choose 2", "combinatorics", "10"),
        ("5!", "combinatorics", "120"),
        ("determinant [[1,2],[3,4]]", "matrix", "-2"),
        ("sin(30 degrees)", "trig", r"\frac{1}{2}"),
        ("sin(-30 degrees)", "trig", r"- \frac{1}{2}"),
        ("sin(pi/2 + 1)", "trig", r"\cos{\left(1 \right)}"),
        ("sin(1 radians)", "trig", r"\sin{\left(1 \right)}"),
    ],
)
def test_supported_categories_match_the_requested_calculation(text, kind, answer):
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None and intent.kind == kind
    block = math_tools._build_verified_block(intent, Settings(_env_file=None))
    assert block is not None
    assert block.canonical_answer == answer


@pytest.mark.parametrize(
    "text",
    [
        "sin(30)+cos(60)",
        "-sin(30)",
        "2 sin(30)",
        "x sin(30)",
        "x - sin(30)",
        "sin(2x)",
        "sin(pi*x)",
        "binomial n=5.5 k=2 p=0.5",
        "binomial n=5 k=2.5 p=0.5",
        "binomial n=5 k=2 p=2",
        "expected value of 0,1 with probabilities 0.9,0.1",
        "mean of 1/0,3",
        "mean of 1+2,3",
        "weighted mean of [(1,1),(3,3)]",
        "5.5 choose 2",
        "5 choose 2.5",
        "factorial of 5.5",
        "gcd of 1.5 and 2.5",
        "gcd of 1/2 and 3/2",
        "inverse [[1,2],[2,4]]",
        "simplify ratio 0:0",
    ],
)
def test_unsupported_or_invalid_input_never_certifies_a_different_problem(text):
    intent = math_tools.extract_math_intent(text)
    block = math_tools._build_verified_block(intent, Settings(_env_file=None)) if intent else None
    assert block is None or block.canonical_answer is None


def test_matrix_inverse_preserves_exact_fractions():
    intent = math_tools.extract_math_intent("inverse [[1,2],[3,4]]")
    assert intent is not None and intent.kind == "matrix"
    block = math_tools._build_verified_block(intent, Settings(_env_file=None))
    assert block is not None
    assert block.canonical_answer == (
        r"\left[\begin{matrix}-2 & 1\\\frac{3}{2} & - \frac{1}{2}\end{matrix}\right]"
    )
