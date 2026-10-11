"""Typed, solver-owned school fraction procedures."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FractionStep(BaseModel):
    kind: Literal[
        "gcd",
        "equivalent",
        "common_denominator",
        "combine",
        "multiply",
        "reciprocal",
        "convert",
        "quantity",
        "compare",
    ]
    explanation: str
    expression: str
    result: str


class FractionWorkSpec(BaseModel):
    """Exact fraction trace. The client lays it out without recalculating."""

    type: Literal["fraction"] = "fraction"
    operation: Literal[
        "simplify",
        "equivalent",
        "add",
        "subtract",
        "multiply",
        "divide",
        "mixed_to_improper",
        "improper_to_mixed",
        "of_quantity",
        "compare",
    ]
    operands: list[str] = Field(min_length=1, max_length=3)
    answer: str
    exact_numerator: int | None = None
    exact_denominator: int | None = Field(default=None, gt=0)
    steps: list[FractionStep] = Field(min_length=1, max_length=8)
