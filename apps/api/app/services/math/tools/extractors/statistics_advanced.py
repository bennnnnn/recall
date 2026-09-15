"""Bivariate statistics intent extraction with explicit paired data lists."""

from __future__ import annotations

import math
from typing import Literal

from app.models.schemas.math import MathIntent

BivariateStatsOp = Literal[
    "correlation",
    "regression",
    "covariance_sample",
    "covariance_population",
]


def _bracket_data_lists(text: str) -> list[list[float]] | None:
    """Parse two ordinary ``[1,2,3]`` lists; deliberately ignore ``[[matrix]]``."""
    if len(text) > 2000:
        return None
    found: list[list[float]] = []
    i = 0
    while i < len(text) and len(found) < 2:
        start = text.find("[", i)
        if start == -1:
            break
        if start + 1 < len(text) and text[start + 1] == "[":
            i = start + 2
            continue
        end = text.find("]", start + 1)
        if end == -1:
            return None
        body = text[start + 1 : end]
        parts = [part.strip() for part in body.split(",")]
        if len(parts) < 2 or len(parts) > 200 or any(not part for part in parts):
            return None
        try:
            values = [float(part) for part in parts]
        except ValueError:
            return None
        if any(not math.isfinite(value) for value in values):
            return None
        found.append(values)
        i = end + 1
    return found if len(found) == 2 else None


def _bivariate_op(text: str) -> BivariateStatsOp | None:
    lower = text.lower()
    if "correlation" in lower or "pearson" in lower:
        return "correlation"
    if "linear regression" in lower or "regression line" in lower or "line of best fit" in lower:
        return "regression"
    if "covariance" in lower:
        if "population" in lower:
            return "covariance_population"
        # Statistical coursework most often means the sample statistic when a
        # raw sample is supplied. The verified block names it explicitly.
        return "covariance_sample"
    return None


def _extract_bivariate_statistics_intent(cleaned: str) -> MathIntent | None:
    operation = _bivariate_op(cleaned)
    if operation is None:
        return None
    lists = _bracket_data_lists(cleaned)
    if lists is None or len(lists[0]) != len(lists[1]):
        return None
    return MathIntent(
        kind="statistics",
        school_op=f"statistics_{operation}",
        vec_a=lists[0],
        vec_b=lists[1],
        operation="solve",
    )


ADVANCED_STATISTICS_EXTRACTORS = (_extract_bivariate_statistics_intent,)
