from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas.math import MatrixInput
from app.services.math import function_analysis
from app.services.math import solve as math_solve
from app.services.math.solve import MathServiceError
from app.services.math.tools import extract_math_intent


def test_function_domain_and_range_are_verified() -> None:
    assert function_analysis.real_domain("x^2/(x-1)") == (
        r"\left(-\infty, 1\right) \cup \left(1, \infty\right)"
    )
    assert function_analysis.real_range("x^2") == r"\left[0, \infty\right)"


def test_inverse_function_refuses_multivalued_full_domain() -> None:
    assert function_analysis.inverse_function("2*x+3") == r"\frac{x}{2} - \frac{3}{2}"
    with pytest.raises(MathServiceError, match="not single-valued"):
        function_analysis.inverse_function("x^2")


def test_function_composition_is_symbolic_and_exact() -> None:
    assert function_analysis.compose_functions("x^2", "x+1") == r"\left(x + 1\right)^{2}"


def test_function_analysis_intents_do_not_steal_matrix_inverse() -> None:
    domain = extract_math_intent("find the domain of f(x)=1/(x-2)")
    assert domain is not None
    assert domain.kind == "calculus"
    assert domain.school_op == "function_domain"
    assert domain.expr == "1/(x-2)"

    composed = extract_math_intent("find f(g(x)) where f(x)=x^2 and g(x)=x+1")
    assert composed is not None
    assert composed.kind == "calculus"
    assert composed.school_op == "function_compose"
    assert composed.expr == "x^2"
    assert composed.expr2 == "x+1"

    matrix = extract_math_intent("inverse of [[2,0],[0,3]]")
    assert matrix is not None
    assert matrix.kind == "matrix"
    assert matrix.matrix_op == "inverse"


def test_advanced_matrix_operations() -> None:
    rows = [[1, 2], [2, 4]]

    rank = math_solve.compute_matrix(MatrixInput(operation="rank", rows=rows))
    assert rank.result_latex == "1"

    nullspace = math_solve.compute_matrix(MatrixInput(operation="nullspace", rows=rows))
    assert nullspace.result_latex is not None
    assert "operatorname{span}" in nullspace.result_latex

    columnspace = math_solve.compute_matrix(MatrixInput(operation="columnspace", rows=rows))
    assert columnspace.result_latex is not None
    assert "operatorname{span}" in columnspace.result_latex

    rowspace = math_solve.compute_matrix(MatrixInput(operation="rowspace", rows=rows))
    assert rowspace.result_latex is not None
    assert "operatorname{span}" in rowspace.result_latex


def test_eigenvectors_and_diagonalization() -> None:
    rows = [[2, 0], [0, 3]]
    eigenvectors = math_solve.compute_matrix(MatrixInput(operation="eigenvectors", rows=rows))
    assert eigenvectors.result_latex is not None
    assert r"\lambda=2" in eigenvectors.result_latex
    assert r"\lambda=3" in eigenvectors.result_latex

    diagonalized = math_solve.compute_matrix(MatrixInput(operation="diagonalize", rows=rows))
    assert diagonalized.result_latex is not None
    assert "P=" in diagonalized.result_latex
    assert "D=" in diagonalized.result_latex


def test_matrix_extraction_recognizes_new_operations() -> None:
    for prompt, operation in (
        ("rank of [[1,2],[2,4]]", "rank"),
        ("nullspace of [[1,2],[2,4]]", "nullspace"),
        ("column space of [[1,2],[2,4]]", "columnspace"),
        ("row space of [[1,2],[2,4]]", "rowspace"),
        ("eigenvectors of [[2,0],[0,3]]", "eigenvectors"),
        ("diagonalize [[2,0],[0,3]]", "diagonalize"),
    ):
        intent = extract_math_intent(prompt)
        assert intent is not None, prompt
        assert intent.kind == "matrix", prompt
        assert intent.matrix_op == operation, prompt


def test_square_matrix_rules_remain_strict() -> None:
    with pytest.raises(ValidationError):
        MatrixInput(operation="eigenvectors", rows=[[1, 2, 3], [4, 5, 6]])

    with pytest.raises(MathServiceError, match="not diagonalizable"):
        math_solve.compute_matrix(
            MatrixInput(operation="diagonalize", rows=[[1, 1], [0, 1]])
        )
