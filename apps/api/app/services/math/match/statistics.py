"""Matchers for paired-data statistics that require two explicit numeric lists."""

from __future__ import annotations

import re
from typing import Literal

from app.services.math.match.discrete import numeric_data_values

BivariateStatsOp = Literal["correlation", "covariance", "linear_regression"]

_LIST_RE = re.compile(r"\[([^\[\]]+)\]")


def _paired_numeric_lists(text: str) -> tuple[list[float], list[float]] | None:
    """Read exactly two explicit ``[...]`` numeric lists of equal length."""
    if "[[" in text:
        return None
    matches = list(_LIST_RE.finditer(text))
    if len(matches) != 2:
        return None
    first = numeric_data_values(matches[0].group(1))
    second = numeric_data_values(matches[1].group(1))
    if first is None or second is None or len(first) != len(second):
        return None
    if len(first) < 2:
        return None
    return first, second


def bivariate_stats_signal(
    text: str,
) -> tuple[BivariateStatsOp, list[float], list[float]] | None:
    """Recognize Pearson correlation, sample covariance, or simple regression.

    The two data series must be explicit bracketed lists. That restriction is
    deliberate: paired statistics are easy to misread from ordinary prose or
    from a single unlabelled stream of numbers.
    """
    lower = text.lower()
    operation: BivariateStatsOp | None = None
    if "correlation" in lower or "pearson" in lower:
        operation = "correlation"
    elif "covariance" in lower:
        operation = "covariance"
    elif any(
        phrase in lower
        for phrase in ("linear regression", "regression line", "best fit line", "line of best fit")
    ):
        operation = "linear_regression"
    if operation is None:
        return None
    paired = _paired_numeric_lists(text)
    if paired is None:
        return None
    return operation, paired[0], paired[1]
