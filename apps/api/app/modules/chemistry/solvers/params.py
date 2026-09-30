"""Typed reads of ``ChemistryIntent.params`` for solvers.

A value the extractor did not find is a refusal, never a default: ``params.get(key) or 1``
turns "the question never gave a concentration" into a verified answer about 1 M.
"""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.services.solving import SolveServiceError


def require(
    intent: ChemistryIntent,
    key: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
    message: str | None = None,
) -> float:
    """``params[key]`` as a float; raise ``SolveServiceError`` when absent or out of range."""
    value = intent.params.get(key)
    if value is None:
        raise SolveServiceError(message or f"{key} is required")
    if positive and value <= 0:
        raise SolveServiceError(message or f"{key} must be positive")
    if non_negative and value < 0:
        raise SolveServiceError(message or f"{key} cannot be negative")
    return float(value)
