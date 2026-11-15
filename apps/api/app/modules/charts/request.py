"""What a chart of the user's data shows, as the read copies it from their words."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ChartKind = Literal["bar", "pie", "line", "histogram", "none"]

# A chart a phone can read: a few dozen bars, a class's worth of scores.
MAX_POINTS = 40
MAX_VALUES = 200


class ChartPoint(BaseModel):
    """One category and its number, both as the user wrote them."""

    label: str = Field(max_length=60)
    value: str = Field(max_length=24)


class ChartRequest(BaseModel):
    kind: ChartKind = "none"
    # What the labels are ("month") and what the numbers measure ("sales"), in the user's
    # words; an axis is titled only with words the user wrote (``grounding``).
    label_name: str = Field(default="", max_length=40)
    value_name: str = Field(default="", max_length=40)
    # bar, pie, line: one number per category.
    points: list[ChartPoint] = Field(default_factory=list, max_length=MAX_POINTS)
    # histogram: the raw values, in the order written.
    values: list[str] = Field(default_factory=list, max_length=MAX_VALUES)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        return text if text in {"bar", "pie", "line", "histogram"} else "none"

    @field_validator("values", mode="before")
    @classmethod
    def _values(cls, value: object) -> list[str]:
        return [str(item) for item in value] if isinstance(value, list) else []
