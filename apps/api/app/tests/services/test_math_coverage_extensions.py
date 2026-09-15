"""Coverage that remains unique after the main math expansion landed."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import tools as math_tools
from app.services.math.coverage_extensions import (
    function_parity,
    matrix_columns_independent,
    matrix_nullity,
)
from app.services.math.solve import compute_bivariate_statistics


@pytest.mark.parametrize(
    "expression,expected",
    [("x^2+1", "even"), ("x^3-x", "odd"), ("x^2+x", "neither")],
)
def test_function_parity(expression: str, expected: str) -> None:
    assert function_parity(expression) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("is f(x)=x^2+1 even or odd?", "even"),
        ("is f(x)=x^3-x odd or even?", "odd"),
    ],
)
def test_function_parity_routes_to_verified_answer(text: str, expected: str) -> None:
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.school_op == "function_even_odd"
    block = math_tools._build_verified_block(intent, Settings())
    assert block is not None
    assert block.canonical_answer == expected


def test_parity_words_in_prose_do_not_trigger_math() -> None:
    assert not math_tools.needs_symbolic_math("the teams had even odds before the game")


def test_matrix_nullity() -> None:
    assert matrix_nullity([[1, 2], [2, 4]]) == "1"


def test_matrix_column_independence() -> None:
    assert matrix_columns_independent([[1, 0], [0, 1]]) == "yes"
    assert matrix_columns_independent([[1, 2], [2, 4]]) == "no"


@pytest.mark.parametrize(
    "text,school_op,answer",
    [
        ("nullity of [[1,2],[2,4]]", "matrix_nullity", "1"),
        (
            "are the columns of [[1,0],[0,1]] linearly independent",
            "matrix_independent_columns",
            "yes",
        ),
    ],
)
def test_matrix_extensions_route_to_verified_answer(
    text: str,
    school_op: str,
    answer: str,
) -> None:
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "matrix"
    assert intent.school_op == school_op
    block = math_tools._build_verified_block(intent, Settings())
    assert block is not None
    assert block.canonical_answer == answer


def test_regression_keeps_canonical_line_and_adds_r_squared() -> None:
    answer, steps = compute_bivariate_statistics(
        "linear_regression",
        [1, 2, 3],
        [2, 4, 6],
    )
    assert answer == "y = 2x"
    assert "Coefficient of determination: R^2 = 1" in steps

    intent = math_tools.extract_math_intent("linear regression for [1,2,3] and [2,4,6]")
    assert intent is not None
    block = math_tools._build_verified_block(intent, Settings())
    assert block is not None
    assert block.canonical_answer == "y = 2x"
    assert "R^2 = 1" in block.text
