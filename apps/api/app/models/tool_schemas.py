"""Pydantic schemas for MCP tool-loop arguments."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WebSearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class SympyToolInput(BaseModel):
    action: Literal["solve", "simplify", "diff", "integrate", "rectangle", "graph"] = "solve"
    lhs: str | None = None
    rhs: str | None = None
    expr: str | None = None
    text: str | None = None
    variables: list[str] = Field(default_factory=lambda: ["x"])
    width: float | None = None
    height: float | None = None
    unit: str = "cm"
    variable: str = "x"
    x_min: float = -10
    x_max: float = 10


class CalendarConflictsInput(BaseModel):
    action: Literal["conflicts"] = "conflicts"
    due_at: str = Field(min_length=1, max_length=64)
    events: list[dict] = Field(default_factory=list)
