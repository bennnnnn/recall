"""Validate geometry/graph fences in assistant output."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.models.math_schemas import (
    GeometryBlockSpec,
    GraphBlockSpec,
    RightTriangleGeometryBlockSpec,
    TriangleGeometryBlockSpec,
)

_GEOMETRY_FENCE = re.compile(r"```geometry\s*\n([\s\S]*?)```", re.IGNORECASE)
_GRAPH_FENCE = re.compile(r"```graph\s*\n([\s\S]*?)```", re.IGNORECASE)


def _validate_geometry(raw: str) -> bool:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return False
        kind = data.get("type")
        if kind in {"rectangle", "rect", "square"}:
            GeometryBlockSpec.model_validate(data)
            return True
        if kind == "triangle":
            TriangleGeometryBlockSpec.model_validate(data)
            return True
        if kind == "right_triangle":
            RightTriangleGeometryBlockSpec.model_validate(data)
            return True
        return False
    except (json.JSONDecodeError, ValidationError, TypeError):
        return False


def _replace_fence(match: re.Match[str], label: str) -> str:
    raw = match.group(1).strip()
    try:
        if label == "geometry":
            if not _validate_geometry(raw):
                raise ValueError("invalid geometry")
        else:
            GraphBlockSpec.model_validate(json.loads(raw))
        return match.group(0)
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        return f"\n> [!WARNING] Invalid {label} block — could not render diagram.\n"


def validate_math_fences(content: str) -> str:
    content = _GEOMETRY_FENCE.sub(lambda m: _replace_fence(m, "geometry"), content)
    return _GRAPH_FENCE.sub(lambda m: _replace_fence(m, "graph"), content)
