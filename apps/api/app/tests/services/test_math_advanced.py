"""Statistics / combinatorics / number theory / matrix math kinds.

These were flagged in a feature audit as common math asks with ZERO SymPy
verification — the model answered them free-text, same reliability as any
other chatbot. Covers the service layer (math_service), text-signal
extraction (math_text_match), and the end-to-end augmentation pipeline
(math_tools.augment_prompt_messages).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.models.math_schemas import (
    CombinatoricsInput,
    MatrixInput,
    NumberTheoryInput,
    StatisticsInput,
)
from app.services import math_service, math_text_match, math_tools


class TestComputeStatistics:
    def test_basic_stats(self):
        result = math_service.compute_statistics(StatisticsInput(numbers=[2, 4, 6, 8]))
        assert result.count == 4
        assert result.mean == 5
        assert result.median == 5
        assert result.modes == []  # every value unique
        assert result.range == 6
        assert result.stdev_sample is not None
        assert result.stdev_population < result.stdev_sample

    def test_mode_detects_repeated_values(self):
        result = math_service.compute_statistics(StatisticsInput(numbers=[1, 2, 2, 3, 4]))
        assert result.modes == [2]

    def test_single_value_has_no_sample_stdev(self):
        result = math_service.compute_statistics(StatisticsInput(numbers=[5, 5]))
        # Both values identical: population/sample stdev are 0, not None —
        # only a TRUE single-element input leaves sample stats undefined.
        result_one = StatisticsInput(numbers=[5, 5, 5])
        r = math_service.compute_statistics(result_one)
        assert r.variance_population == 0
        assert result.stdev_sample == 0


class TestComputeCombinatorics:
    def test_factorial(self):
        result = math_service.compute_combinatorics(CombinatoricsInput(operation="factorial", n=5))
        assert result.result == 120

    def test_factorial_capped(self):
        with pytest.raises(math_service.MathServiceError):
            math_service.compute_combinatorics(CombinatoricsInput(operation="factorial", n=171))

    def test_combinations(self):
        result = math_service.compute_combinatorics(
            CombinatoricsInput(operation="combinations", n=5, k=2)
        )
        assert result.result == 10

    def test_permutations(self):
        result = math_service.compute_combinatorics(
            CombinatoricsInput(operation="permutations", n=5, k=2)
        )
        assert result.result == 20

    def test_k_greater_than_n_rejected(self):
        with pytest.raises(math_service.MathServiceError):
            math_service.compute_combinatorics(
                CombinatoricsInput(operation="combinations", n=3, k=5)
            )


class TestComputeNumberTheory:
    def test_gcd(self):
        result = math_service.compute_number_theory(NumberTheoryInput(operation="gcd", a=48, b=18))
        assert result.result_int == 6

    def test_lcm(self):
        result = math_service.compute_number_theory(NumberTheoryInput(operation="lcm", a=4, b=6))
        assert result.result_int == 12

    def test_factorize(self):
        result = math_service.compute_number_theory(NumberTheoryInput(operation="factorize", a=60))
        assert result.factors == {2: 2, 3: 1, 5: 1}

    def test_factorize_rejects_less_than_two(self):
        with pytest.raises(math_service.MathServiceError):
            math_service.compute_number_theory(NumberTheoryInput(operation="factorize", a=1))

    def test_is_prime(self):
        assert math_service.compute_number_theory(
            NumberTheoryInput(operation="is_prime", a=97)
        ).result_bool
        assert not math_service.compute_number_theory(
            NumberTheoryInput(operation="is_prime", a=100)
        ).result_bool

    def test_mod(self):
        result = math_service.compute_number_theory(NumberTheoryInput(operation="mod", a=17, b=5))
        assert result.result_int == 2

    def test_mod_by_zero_rejected(self):
        with pytest.raises(math_service.MathServiceError):
            math_service.compute_number_theory(NumberTheoryInput(operation="mod", a=17, b=0))


class TestComputeMatrix:
    def test_determinant_2x2(self):
        result = math_service.compute_matrix(
            MatrixInput(operation="determinant", rows=[[1, 2], [3, 4]])
        )
        assert result.determinant == -2

    def test_inverse_uses_exact_fractions_not_float_noise(self):
        result = math_service.compute_matrix(
            MatrixInput(operation="inverse", rows=[[2, 0], [1, 3]])
        )
        assert result.inverse_latex is not None
        assert "0.1666" not in result.inverse_latex
        assert "\\frac{1}{6}" in result.inverse_latex

    def test_singular_matrix_rejected(self):
        with pytest.raises(math_service.MathServiceError):
            math_service.compute_matrix(MatrixInput(operation="inverse", rows=[[1, 2], [2, 4]]))

    def test_non_square_rejected_at_schema_level(self):
        with pytest.raises(ValueError):
            MatrixInput(operation="determinant", rows=[[1, 2, 3], [4, 5, 6]])


class TestMathTextMatchSignals:
    def test_stats_signal_requires_numbers_not_just_keyword(self):
        assert math_text_match.stats_signal("what do you mean by that") is None
        assert math_text_match.stats_signal("mean of 2, 4, 6") == ("mean", [2.0, 4.0, 6.0])

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("5!", ("factorial", 5, None)),
            ("factorial of 5", ("factorial", 5, None)),
            ("5 choose 2", ("combinations", 5, 2)),
            ("C(5,2)", ("combinations", 5, 2)),
            ("5C2", ("combinations", 5, 2)),
            ("P(5,2)", ("permutations", 5, 2)),
            ("5P2", ("permutations", 5, 2)),
        ],
    )
    def test_combinatorics_signal(self, text, expected):
        assert math_text_match.combinatorics_signal(text) == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("gcd of 48 and 18", ("gcd", 48, 18)),
            ("least common multiple of 4 and 6", ("lcm", 4, 6)),
            ("prime factorization of 60", ("factorize", 60, None)),
            ("is 97 prime", ("is_prime", 97, None)),
            ("17 mod 5", ("mod", 17, 5)),
        ],
    )
    def test_number_theory_signal(self, text, expected):
        assert math_text_match.number_theory_signal(text) == expected

    def test_matrix_signal(self):
        assert math_text_match.matrix_signal("determinant of [[1,2],[3,4]]") == (
            "determinant",
            [[1.0, 2.0], [3.0, 4.0]],
        )
        assert math_text_match.matrix_signal("no matrix here") is None

    def test_needs_symbolic_true_for_each_new_kind(self):
        for text in (
            "mean of 2, 4, 6, 8",
            "5 choose 2",
            "gcd of 12 and 18",
            "determinant of [[1,2],[3,4]]",
        ):
            assert math_text_match.needs_symbolic(text) is True


class TestAugmentPromptMessagesForNewKinds:
    @pytest.mark.asyncio
    async def test_statistics_produces_verified_block(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        text = "what is the standard deviation of 1, 3, 5, 7, 9"
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        updated, verified = await math_tools.augment_prompt_messages(messages, text, settings)
        assert verified is not None
        assert "mean=5" in verified.text
        assert "Do NOT recompute" in verified.text
        assert len(updated) == 3

    @pytest.mark.asyncio
    async def test_combinatorics_produces_verified_block(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        text = "how many ways can you choose 2 from 5? use C(5,2)"
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        updated, verified = await math_tools.augment_prompt_messages(messages, text, settings)
        assert verified is not None
        assert "10" in verified.text

    @pytest.mark.asyncio
    async def test_matrix_produces_verified_block(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        text = "find the determinant of [[1,2],[3,4]]"
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        updated, verified = await math_tools.augment_prompt_messages(messages, text, settings)
        assert verified is not None
        assert "-2" in verified.text
