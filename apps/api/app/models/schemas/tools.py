"""Pydantic schemas for MCP tool-loop arguments."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# A graph's x-range when the call names none: the school window.
_GRAPH_X_MIN, _GRAPH_X_MAX = -10.0, 10.0


class WebSearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    recent: bool = Field(
        default=True,
        description=(
            "Only pages from the last year are searched, for how things stand now. false "
            "only for a question about the past (an earlier year, a historical event)"
        ),
    )


class RecallChatsToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class SympyToolInput(BaseModel):
    action: Literal[
        "solve",
        "simplify",
        "diff",
        "integrate",
        "factor",
        "expand",
        "inequality",
        "rectangle",
        "square",
        "circle",
        "graph",
        "system",
        "limit",
        "series",
        "newton",
        "dsolve",
    ] = "solve"
    # Bounded the same as the equivalent fields on EquationInput/GraphSampleInput
    # (apps/api/app/modules/math/schemas/) — unbounded strings here fed straight
    # into math_solve's SymPy parser with no cap of their own.
    lhs: str | None = Field(default=None, max_length=256)
    rhs: str | None = Field(default=None, max_length=256)
    expr: str | None = Field(default=None, max_length=256)
    # graph: optional second curve (sampled server-side — never invent points2).
    expr2: str | None = Field(default=None, max_length=256)
    text: str | None = Field(default=None, max_length=2000)
    variables: list[str] = Field(default_factory=lambda: ["x"], max_length=4)
    width: float | None = None
    height: float | None = None
    # square / circle geometry (printed dimensions — never invent freehand).
    side: float | None = Field(default=None, gt=0, le=1_000_000)
    radius: float | None = Field(default=None, gt=0, le=1_000_000)
    unit: str = "cm"
    variable: str = Field(default="x", max_length=8)
    variable2: str | None = Field(default=None, max_length=8)
    label: str | None = Field(default=None, max_length=64)
    label2: str | None = Field(default=None, max_length=64)
    x_min: float = _GRAPH_X_MIN
    x_max: float = _GRAPH_X_MAX
    # system: list of (lhs, rhs) pairs (mirrors SystemOfEquationsInput).
    equations: list[tuple[str, str]] = Field(default_factory=list, max_length=4)
    # inequality: comparator on lhs/rhs (compound inequalities stay on heuristic path).
    comparator: Literal["<", ">", "<=", ">="] | None = None
    # limit: the point the variable approaches (+ direction "+-"/"+"/"-").
    point: str | None = Field(default=None, max_length=32)
    direction: str = Field(default="+-", max_length=4)
    # series: bounds (infinity-aware — "oo"/"inf"/"infty" accepted).
    start: str | None = Field(default=None, max_length=32)
    end: str | None = Field(default=None, max_length=32)
    # integrate: definite bounds (prefer these over start/end for clarity).
    lower: str | None = Field(default=None, max_length=32)
    upper: str | None = Field(default=None, max_length=32)
    # newton: initial guess.
    guess: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    # diff: 1 = first derivative; 2 = second, …
    order: int = Field(default=1, ge=1, le=4)


def _bound(value: Any, default: float) -> tuple[float, bool]:
    """A bound the call gives, or the default and False when it gives none."""
    if value is None or value == "":
        return default, False
    return float(value), True


def graph_range(args: dict[str, Any]) -> tuple[float, float, bool]:
    """A ``sympy`` graph call's ``x_min`` and ``x_max``, and whether it named both. A range
    the call names is the learner's ("for x from 0 to 12"): 0 is a bound, not a missing one
    (``or -10`` read it as -10), and the card opens on that range (``domain_explicit``).
    The textbook's y = 2x + 1 "for x from -3 to 3" opened on the school window, cutting the
    line off (2026-11-13)."""
    x_min, low = _bound(args.get("x_min"), _GRAPH_X_MIN)
    x_max, high = _bound(args.get("x_max"), _GRAPH_X_MAX)
    return x_min, x_max, low and high


class GenerateImageToolInput(BaseModel):
    """Model-initiated image generation (Pro; tool loop only)."""

    prompt: str = Field(min_length=1, max_length=2000)
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:3", "3:4"] | None = None
    reference_attachment_ids: list[UUID] | None = Field(default=None, max_length=2)


class ImageSearchToolInput(BaseModel):
    """Model-initiated reference-photo lookup (free + pro; tool loop only)."""

    query: str = Field(min_length=1, max_length=200)
