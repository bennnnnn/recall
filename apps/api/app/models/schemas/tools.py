"""Pydantic schemas for MCP tool-loop arguments."""

from __future__ import annotations

import json
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.schemas.job_search import (
    JobMatchStatus,
    JobSearchPreferencesPatch,
    JobSearchStatus,
)


class WebSearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class JobSearchToolInput(BaseModel):
    action: Literal[
        "list",
        "get_profile",
        "update_profile",
        "update_status",
        "search_now",
        "analyze_job",
        "update_match",
    ] = "list"
    preferences: JobSearchPreferencesPatch | None = None
    result_limit: int | None = Field(
        default=None,
        ge=1,
        le=15,
        description="Maximum verified jobs for this one search; does not change the saved profile.",
    )
    search_status: JobSearchStatus | None = None
    job_url: str | None = Field(default=None, max_length=2000)
    match_id: UUID | None = None
    match_status: JobMatchStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def decode_stringified_preferences(cls, value: object) -> object:
        """Normalize providers that serialize the nested preference object.

        Some function-calling providers emit a compact ``key: value`` string
        even though the advertised schema requires an object. Keep the parser
        deliberately bounded to known preference labels so malformed or
        ambiguous updates still fail validation instead of being guessed.
        """
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        preferences = normalized.get("preferences")
        if not isinstance(preferences, str):
            return normalized
        try:
            decoded = json.loads(preferences)
        except (TypeError, ValueError):
            decoded = None
        if isinstance(decoded, dict):
            normalized["preferences"] = decoded
            return normalized

        label_aliases = {
            "role": "target_roles",
            "roles": "target_roles",
            "target role": "target_roles",
            "target roles": "target_roles",
            "skill": "skills",
            "skills": "skills",
            "location": "location",
            "locations": "location",
            "work mode": "work_modes",
            "work modes": "work_modes",
            "work style": "work_modes",
            "work type": "work_modes",
            "experience": "experience_levels",
            "experience level": "experience_levels",
            "experience levels": "experience_levels",
            "excluded company": "excluded_companies",
            "excluded companies": "excluded_companies",
            "frequency": "frequency",
        }
        parsed: dict[str, object] = {}
        compact = preferences.strip().removeprefix("{").removesuffix("}")
        labels_pattern = "|".join(re.escape(label) for label in label_aliases)
        compact = re.sub(
            rf",\s*(?=(?:{labels_pattern.replace(r'\ ', r'[ _]')})\s*:)",
            ";",
            compact,
            flags=re.IGNORECASE,
        )
        segments = [segment.strip() for segment in compact.replace("\n", ";").split(";")]
        for segment in segments:
            if not segment:
                continue
            label, separator, raw_value = segment.partition(":")
            if not separator:
                label, separator, raw_value = segment.partition("=")
            normalized_label = " ".join(label.strip().casefold().replace("_", " ").split())
            canonical = label_aliases.get(normalized_label)
            clean_value = raw_value.strip()
            if not separator or canonical is None or not clean_value:
                return normalized
            if canonical in {
                "target_roles",
                "skills",
                "work_modes",
                "experience_levels",
                "excluded_companies",
            }:
                parsed[canonical] = [
                    item.strip() for item in clean_value.split(",") if item.strip()
                ]
            else:
                parsed[canonical] = clean_value
        if parsed:
            normalized["preferences"] = parsed
        return normalized


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
    # (apps/api/app/models/schemas/math/) — unbounded strings here fed straight
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
    x_min: float = -10
    x_max: float = 10
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


class CalendarConflictEvent(BaseModel):
    """Bounded calendar event stub for conflict checks (model-supplied)."""

    start: str | None = Field(default=None, max_length=64)
    end: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=200)


class CalendarConflictsInput(BaseModel):
    action: Literal["conflicts"] = "conflicts"
    due_at: str = Field(min_length=1, max_length=64)
    events: list[CalendarConflictEvent] = Field(default_factory=list, max_length=50)


class GenerateImageToolInput(BaseModel):
    """Model-initiated image generation (Pro; tool loop only)."""

    prompt: str = Field(min_length=1, max_length=2000)
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:3", "3:4"] | None = None
    reference_attachment_ids: list[UUID] | None = Field(default=None, max_length=2)


class ImageSearchToolInput(BaseModel):
    """Model-initiated reference-photo lookup (free + pro; tool loop only)."""

    query: str = Field(min_length=1, max_length=200)
