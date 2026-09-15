"""Verified correlation, covariance, and linear-regression coverage."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math import tools as math_tools
from app.services.math.solve import MathServiceError
from app.services.math.solve.advanced import compute_bivariate_statistics


def test_pearson_correlation_perfect_positive() -> None:
    answer, steps = compute_bivariate_statistics([1, 2, 3], [2, 4, 6], "correlation")
    assert answer == "1"
    assert steps == ["Pearson r = 1"]


def test_sample_and_population_covariance_are_distinct() -> None:
    sample, _ = compute_bivariate_statistics([1, 2, 3], [2, 4, 6], "covariance_sample")
    population, _ = compute_bivariate_statistics(
        [1, 2, 3], [2, 4, 6], "covariance_population"
    )
    assert sample == "2"
    assert population.startswith("1.333333")


def test_linear_regression() -> None:
    answer, steps = compute_bivariate_statistics([1, 2, 3], [2, 4, 6], "regression")
    assert answer == "y = 2x + 0"
    assert "least-squares slope = 2" in steps


def test_correlation_refuses_constant_series() -> None:
    with pytest.raises(MathServiceError):
        compute_bivariate_statistics([1, 1, 1], [2, 3, 4], "correlation")


def test_regression_refuses_constant_x() -> None:
    with pytest.raises(MathServiceError):
        compute_bivariate_statistics([1, 1, 1], [2, 3, 4], "regression")


@pytest.mark.parametrize(
    "text,school_op",
    [
        ("correlation of [1,2,3] and [2,4,6]", "statistics_correlation"),
        ("Pearson correlation for [1,2,3] and [2,4,6]", "statistics_correlation"),
        ("linear regression of [1,2,3] and [2,4,6]", "statistics_regression"),
        ("covariance of [1,2,3] and [2,4,6]", "statistics_covariance_sample"),
        (
            "population covariance of [1,2,3] and [2,4,6]",
            "statistics_covariance_population",
        ),
    ],
)
def test_bivariate_statistics_extracts(text: str, school_op: str) -> None:
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "statistics"
    assert intent.school_op == school_op
    assert intent.vec_a == [1.0, 2.0, 3.0]
    assert intent.vec_b == [2.0, 4.0, 6.0]


def test_correlation_word_alone_does_not_trigger_math() -> None:
    assert not math_tools.needs_symbolic_math("correlation is not causation")


def test_mismatched_data_lists_do_not_get_verified() -> None:
    text = "correlation of [1,2,3] and [2,4]"
    assert not math_tools.needs_symbolic_math(text)
    assert math_tools.extract_math_intent(text) is None


def test_correlation_builds_verified_answer() -> None:
    settings = Settings(math_tools_enabled=True)
    intent = math_tools.extract_math_intent("correlation of [1,2,3] and [2,4,6]")
    assert intent is not None
    block = math_tools._build_verified_block(intent, settings)
    assert block is not None
    assert block.canonical_answer == "1"
    assert "Pearson r = 1" in block.text
