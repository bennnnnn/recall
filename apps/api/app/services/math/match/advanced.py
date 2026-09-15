"""Cheap cues for advanced verified math features.

The actual parsing lives in ``math.tools.extractors.advanced``.  This module is
kept dependency-light because ``match.needs`` imports it on every chat turn.
"""

from __future__ import annotations


def advanced_cue(text: str) -> bool:
    """Return True when *text* is worth offering to the advanced extractors.

    These are deliberately cues, not claims that the request is supported.
    Extractors still require complete, explicit operands before a verified
    block can be produced.
    """
    if not text or len(text) > 1000:
        return False
    lower = text.lower()

    if "[[" in text and any(
        cue in lower
        for cue in (
            "rank",
            "nullspace",
            "null space",
            "nullity",
            "column space",
            "row space",
            "eigenvector",
            "diagonalize",
            "diagonalise",
            "linearly independent",
        )
    ):
        return True

    if text.count("[") >= 2 and any(
        cue in lower
        for cue in (
            "correlation",
            "pearson",
            "covariance",
            "linear regression",
            "regression line",
            "line of best fit",
            "least squares line",
        )
    ):
        return True

    function_cue = any(
        cue in lower
        for cue in (
            "domain of",
            "range of",
            "inverse function",
            "inverse of f(",
            "even or odd",
            "odd or even",
            "f(g(x))",
            "g(f(x))",
        )
    )
    if function_cue and any(token in lower for token in ("x", "f(", "g(", "y=")):
        return True

    if "area between" in lower and (" from " in lower or " on [" in lower):
        return True
    if "arc length" in lower and (" from " in lower or " on [" in lower):
        return True
    if "volume" in lower and ("revolution" in lower or "revolved" in lower or "rotated" in lower):
        return "axis" in lower and " from " in lower

    return False
