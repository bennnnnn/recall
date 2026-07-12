"""Pydantic schemas for MCP tool-loop arguments."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WebSearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class SympyToolInput(BaseModel):
    action: Literal["solve", "simplify", "diff", "integrate", "rectangle", "graph"] = "solve"
    # Bounded the same as the equivalent fields on EquationInput/GraphSampleInput
    # (apps/api/app/models/math_schemas.py) — unbounded strings here fed straight
    # into math_service's SymPy parser with no cap of their own.
    lhs: str | None = Field(default=None, max_length=256)
    rhs: str | None = Field(default=None, max_length=256)
    expr: str | None = Field(default=None, max_length=256)
    text: str | None = Field(default=None, max_length=2000)
    variables: list[str] = Field(default_factory=lambda: ["x"], max_length=4)
    width: float | None = None
    height: float | None = None
    unit: str = "cm"
    variable: str = Field(default="x", max_length=8)
    x_min: float = -10
    x_max: float = 10


class CalendarConflictsInput(BaseModel):
    action: Literal["conflicts"] = "conflicts"
    due_at: str = Field(min_length=1, max_length=64)
    events: list[dict] = Field(default_factory=list)
