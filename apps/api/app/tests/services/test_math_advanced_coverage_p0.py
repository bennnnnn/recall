"""Regression coverage for the P0 advanced verified-math expansion.

The important contract is not just that SymPy can compute these results.  A
request must enter the verified pipeline only when all operands are explicit,
and unrelated prose must continue to miss the math gate.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import match as math_match
from app.services.math import tools as math_tools
from app.services.math.solve.advanced import (
    solve_bivariate_statistics,
    solve_calculus_application,
    solve_function_feature,
    solve_matrix_feature,
)
from app.services.math.tools.extract import extract_math_intent


class TestAdvancedSolvers:
    def test_function_domain(self):
        answer = solve_function_feature("function_domain", "1/(x-2)")
        assert "2" in answer
        assert "\\cup" in answer

    def test_function_inverse_requires_one_real_branch(self):
        answer = solve_function_feature("function_inverse", "2*x+1")
        assert "f^{-1}(x)" in answer
        assert "\\frac{x}{2}" in answer
        with pytest.raises(math_tools.MathServiceError):
            solve_function_feature("function_inverse", "x^2")

    def test_function_symmetry_and_composition(self):
        assert solve_function_feature("function_even_odd", "x^3") == "odd"
        composed = solve_function_feature("function_compose_fg", "x+1", "x^2")
        assert "x^{2} + 1" in composed

    def test_matrix_rank_nullity_and_independence(self):
        rows = [[1, 2], [2, 4]]
        assert solve_matrix_feature("matrix_rank", rows) == "1"
        assert solve_matrix_feature("matrix_nullity", rows) == "1"
        assert solve_matrix_feature("matrix_independent_columns", rows) == "no"

    def test_matrix_eigenvectors(self):
        answer = solve_matrix_feature("matrix_eigenvectors", [[2, 0], [0, 3]])
        assert "\\lambda=2" in answer
        assert "\\lambda=3" in answer

    def test_correlation_and_regression(self):
        xs = [1, 2, 3]
        ys = [2, 4, 6]
        assert solve_bivariate_statistics("correlation", xs, ys) == "1"
        regression = solve_bivariate_statistics("linear_regression", xs, ys)
        assert regression.startswith("y = 2x + 0")
        assert "R^2 = 1" in regression

    def test_calculus_applications(self):
        area = solve_calculus_application("area_between_curves", "x", "0", "1", "x^2")
        assert area == "\\frac{1}{6}"
        volume = solve_calculus_application("volume_revolution_x", "x", "0", "1")
        assert volume == "\\frac{\\pi}{3}"


class TestAdvancedExtraction:
    def test_function_domain_intent(self):
        intent = extract_math_intent("domain of f(x)=1/(x-2)")
        assert intent is not None
        assert intent.kind == "calculus"
        assert intent.school_op == "function_domain"
        assert intent.expr == "1/(x-2)"

    def test_matrix_rank_intent(self):
        intent = extract_math_intent("rank of [[1,2],[2,4]]")
        assert intent is not None
        assert intent.kind == "matrix"
        assert intent.school_op == "matrix_rank"

    def test_bivariate_statistics_intent(self):
        intent = extract_math_intent("correlation of [1,2,3] and [2,4,6]")
        assert intent is not None
        assert intent.kind == "statistics"
        assert intent.school_op == "correlation"
        assert intent.vec_a == [1.0, 2.0, 3.0]
        assert intent.vec_b == [2.0, 4.0, 6.0]

    def test_area_between_curves_intent(self):
        intent = extract_math_intent("area between y=x and y=x^2 from 0 to 1")
        assert intent is not None
        assert intent.kind == "calculus"
        assert intent.school_op == "area_between_curves"
        assert intent.expr == "x"
        assert intent.expr2 == "x^2"
        assert intent.integral_lower == "0"
        assert intent.integral_upper == "1"

    @pytest.mark.parametrize(
        "text",
        [
            "rank of [[1,2],[2,4]]",
            "correlation of [1,2,3] and [2,4,6]",
            "domain of f(x)=1/(x-2)",
            "area between y=x and y=x^2 from 0 to 1",
        ],
    )
    def test_needs_symbolic_for_advanced_requests(self, text):
        assert math_match.needs_symbolic(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "what is the rank structure at my company?",
            "what is the range of this product?",
            "we need a regression plan for the release",
        ],
    )
    def test_unrelated_prose_does_not_trigger_advanced_math(self, text):
        assert math_match.needs_symbolic(text) is False

    def test_existing_inverse_routes_are_not_stolen(self):
        modular = extract_math_intent("modular inverse of 3 mod 11")
        assert modular is not None
        assert modular.kind == "number_theory"
        assert modular.numtheory_op == "mod_inverse"

        matrix = extract_math_intent("inverse of [[2,0],[1,3]]")
        assert matrix is not None
        assert matrix.kind == "matrix"
        assert matrix.matrix_op == "inverse"


class TestAdvancedVerifiedPipeline:
    @pytest.mark.asyncio
    async def test_matrix_rank_produces_verified_answer(self):
        settings = Settings(
            mcp_tools_enabled=False,
            web_search_enabled=False,
            math_tools_enabled=True,
        )
        text = "rank of [[1,2],[2,4]]"
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        updated, verified = await math_tools.augment_prompt_messages(messages, text, settings)

        assert verified is not None
        assert "Rank: 1" in verified.text
        assert verified.canonical_answer == "1"
        assert verified.canonical_fence is not None
        assert verified.canonical_fence["type"] == "answer"
        assert len(updated) == 3
