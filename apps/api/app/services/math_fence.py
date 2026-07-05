"""Validate geometry/graph fences in assistant output.

Schema validity alone doesn't mean the *numbers* are right — the model is
only asked (in the system prompt) to copy the SymPy-computed fence
verbatim, not structurally forced to. When the turn actually computed a
canonical fence (``VerifiedMathBlock.canonical_fence``), a same-kind fence
in the model's output is replaced with the canonical JSON outright, so a
drifted or hallucinated number never reaches the user even inside an
otherwise schema-valid block.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.models.math_schemas import (
    GeometryBlockSpec,
    GraphBlockSpec,
    RightTriangleGeometryBlockSpec,
    TriangleGeometryBlockSpec,
)

if TYPE_CHECKING:
    from app.services.math_tools import VerifiedMathBlock

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


def _canonical_replacement(raw: str, canonical_fence: dict[str, object] | None) -> str | None:
    """If a canonical fence exists for this turn and the model's fence is the
    same kind, return the canonical JSON to substitute in — the model's own
    numbers are never trusted once we have the real computed values."""
    if canonical_fence is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("type") != canonical_fence.get("type"):
        return None
    return json.dumps(canonical_fence, separators=(",", ":"))


def _replace_fence(
    match: re.Match[str],
    label: str,
    canonical_fence: dict[str, object] | None,
) -> str:
    raw = match.group(1).strip()
    corrected = _canonical_replacement(raw, canonical_fence)
    if corrected is not None:
        return f"```{label}\n{corrected}\n```"
    try:
        if label == "geometry":
            if not _validate_geometry(raw):
                raise ValueError("invalid geometry")
        else:
            GraphBlockSpec.model_validate(json.loads(raw))
        return match.group(0)
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        return f"\n> [!WARNING] Invalid {label} block — could not render diagram.\n"


def validate_math_fences(content: str, *, verified: VerifiedMathBlock | None = None) -> str:
    canonical_fence = verified.canonical_fence if verified is not None else None
    content = _GEOMETRY_FENCE.sub(lambda m: _replace_fence(m, "geometry", canonical_fence), content)
    return _GRAPH_FENCE.sub(lambda m: _replace_fence(m, "graph", canonical_fence), content)
