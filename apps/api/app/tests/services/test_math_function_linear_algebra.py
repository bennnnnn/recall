"""Verified function-analysis and undergraduate linear-algebra coverage."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import tools as math_tools
from app.services.math.solve.advanced import compute_function_feature, compute_matrix_feature


class TestFunctionFeatures:
    def test_domain(self) -> None:
        answer, steps = compute_function_feature("domain", "sqrt(x-3)")
        assert "3" in answer
        assert "infty" in answer
        assert steps

    def test_range(self) -> None:
        answer, _steps = compute_function_feature("range", "x**2")
        assert "0" in answer
        assert "infty" in answer

    def test_inverse_linear(self) -> None:
        answer, _steps = compute_function_feature("inverse", "2*x+3")
        assert "f^{-1}" in answer
        assert "3" in answer
        assert "2" in answer

    def test_inverse_refuses_multibranch_relation(self) -> None:
        from app.services.math.solve import MathServiceError

        with pytest.raises(MathServiceError):
            compute_function_feature("inverse", "x**2")

    def test_composition(self) -> None:
        answer, _steps = compute_function_feature(
            "composition", "x**2+1", expr2="2*x"
        )
        assert "4" in answer
        assert "x" in answer

    @pytest.mark.parametrize(
        "text,school_op",
        [
            ("find the domain of f(x)=sqrt(x-3)", "function_domain"),
            ("find the range of f(x)=x^2", "function_range"),
            ("find the inverse function of f(x)=2*x+3", "function_inverse"),
            (
                "find f(g(x)) if f(x)=x^2+1 and g(x)=2*x",
                "function_composition",
            ),
        ],
    )
    def test_extracts_function_intent(self, text: str, school_op: str) -> None:
        assert math_tools.needs_symbolic_math(text)
        intent = math_tools.extract_math_intent(text)
        assert intent is not None
        assert intent.kind == "calculus"
        assert intent.school_op == school_op

    def test_domain_builds_verified_answer(self) -> None:
        settings = Settings(math_tools_enabled=True)
        intent = math_tools.extract_math_intent("find the domain of f(x)=sqrt(x-3)")
        assert intent is not None
        block = math_tools._build_verified_block(intent, settings)
        assert block is not None
        assert block.canonical_answer is not None
        assert "3" in block.canonical_answer


class TestAdvancedLinearAlgebra:
    def test_rank(self) -> None:
        answer, steps = compute_matrix_feature([[1, 2], [2, 4]], "rank")
        assert answer == "1"
        assert "rank" in steps[0]

    def test_nullspace(self) -> None:
        answer, _steps = compute_matrix_feature([[1, 2], [2, 4]], "nullspace")
        assert "span" in answer
        assert "2" in answer

    def test_column_and_row_spaces(self) -> None:
        column, _ = compute_matrix_feature([[1, 2], [2, 4]], "columnspace")
        row, _ = compute_matrix_feature([[1, 2], [2, 4]], "rowspace")
        assert "span" in column
        assert "span" in row

    def test_eigenvectors(self) -> None:
        answer, _steps = compute_matrix_feature([[2, 0], [0, 3]], "eigenvectors")
        assert "lambda=2" in answer
        assert "lambda=3" in answer

    def test_diagonalize(self) -> None:
        answer, steps = compute_matrix_feature([[2, 0], [0, 3]], "diagonalize")
        assert "P=" in answer
        assert "D=" in answer
        assert "PDP" in steps[0]

    @pytest.mark.parametrize(
        "text,school_op",
        [
            ("rank of [[1,2],[2,4]]", "matrix_rank"),
            ("nullspace of [[1,2],[2,4]]", "matrix_nullspace"),
            ("column space of [[1,2],[2,4]]", "matrix_columnspace"),
            ("row space of [[1,2],[2,4]]", "matrix_rowspace"),
            ("eigenvectors of [[2,0],[0,3]]", "matrix_eigenvectors"),
            ("diagonalize [[2,0],[0,3]]", "matrix_diagonalize"),
        ],
    )
    def test_extracts_matrix_intent(self, text: str, school_op: str) -> None:
        assert math_tools.needs_symbolic_math(text)
        intent = math_tools.extract_math_intent(text)
        assert intent is not None
        assert intent.kind == "matrix"
        assert intent.school_op == school_op

    def test_rank_builds_verified_answer(self) -> None:
        settings = Settings(math_tools_enabled=True)
        intent = math_tools.extract_math_intent("rank of [[1,2],[2,4]]")
        assert intent is not None
        block = math_tools._build_verified_block(intent, settings)
        assert block is not None
        assert block.canonical_answer == "1"
