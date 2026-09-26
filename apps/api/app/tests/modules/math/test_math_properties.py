"""Property-based tests for the math extractors (Hypothesis).

The extractor registry is a hand-tuned regex decision tree; example tests pin
the cases we already know about. These properties pin the *invariants* over
generated inputs:

- extraction never raises and always returns a schema-valid intent (or None),
- a generated arithmetic prompt extracts an expression whose value matches
  the reference computation,
- a generated linear equation extracts sides symbolically equivalent to the
  generated equation.

Failing minimal examples printed by Hypothesis get pinned as regression tests
in the example-based suites.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.schemas.math import MathIntent
from app.modules.math.match import needs_symbolic
from app.modules.math.solve import _parse_expression
from app.modules.math.tools.extract import extract_math_intent

_SMALL_INT = st.integers(min_value=-50, max_value=50)
_POS_INT = st.integers(min_value=1, max_value=9)


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
        max_size=200,
    )
)
@settings(max_examples=100, deadline=None)
def test_extract_never_raises_and_stays_schema_valid(text: str) -> None:
    """Arbitrary unicode/punctuation soup: no crash, valid intent, deterministic."""
    first = extract_math_intent(text)
    second = extract_math_intent(text)
    assert first == second
    if first is not None:
        # Round-trip through the schema — an extractor must never emit a
        # half-formed intent that Pydantic would reject downstream.
        MathIntent.model_validate(first.model_dump())
    # The gate must survive the same input.
    assert needs_symbolic(text) in (True, False)


@given(a=_SMALL_INT, op=st.sampled_from(["+", "-", "*"]), b=_SMALL_INT)
@settings(max_examples=60, deadline=None, derandomize=True)
def test_generated_arithmetic_extracts_matching_value(a: int, op: str, b: int) -> None:
    text = f"what is {a} {op} {b}"
    intent = extract_math_intent(text)
    assert intent is not None, text
    assert intent.kind == "arithmetic"
    assert intent.expr is not None
    parsed = _parse_expression(intent.expr)
    expected = a + b if op == "+" else (a - b if op == "-" else a * b)
    assert float(parsed) == pytest.approx(expected), text


@given(a=_POS_INT, b=_SMALL_INT, c=_SMALL_INT)
@settings(max_examples=60, deadline=None, derandomize=True)
def test_generated_linear_equation_extracts_equivalent_sides(a: int, b: int, c: int) -> None:
    sign = "+" if b >= 0 else "-"
    text = f"solve {a}x {sign} {abs(b)} = {c}"
    intent = extract_math_intent(text)
    assert intent is not None, text
    assert intent.kind == "equation"
    assert intent.lhs is not None and intent.rhs is not None
    lhs = _parse_expression(intent.lhs, ["x"])
    rhs = _parse_expression(intent.rhs, ["x"])
    reference = _parse_expression(f"{a}*x + ({b}) - ({c})", ["x"])
    assert (lhs - rhs - reference).simplify() == 0, text
