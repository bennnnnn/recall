"""Validate geometry/graph fences in assistant output.

Schema validity alone doesn't mean the *numbers* are right — the model is
only asked (in the system prompt) to copy the SymPy-computed fence
verbatim, not structurally forced to. When the turn actually computed a
canonical fence (``VerifiedMathBlock.canonical_fence``), a same-kind fence
in the model's output is replaced with the canonical JSON outright, so a
drifted or hallucinated number never reaches the user even inside an
otherwise schema-valid block.

When there is no canonical sample, the model still often emits a continuous
`` ```graph `` fence with only a few key points (roots / intercepts). Drawing
those as a polyline makes a quartic look like a V. We densify those sparse
fences by re-sampling the declared expression with SymPy before the client
renders.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    RightTriangleGeometryBlockSpec,
    TriangleGeometryBlockSpec,
)
from app.services import math_service
from app.services.math_service import MathServiceError

if TYPE_CHECKING:
    from app.services.math_tools import VerifiedMathBlock

_GEOMETRY_FENCE = re.compile(r"```geometry\s*\n([\s\S]*?)```", re.IGNORECASE)
_GRAPH_FENCE = re.compile(r"```graph\s*\n([\s\S]*?)```", re.IGNORECASE)

# Below this count a continuous y=f(x) fence is treated as "sparse key points"
# the model listed for prose, not a renderable curve sample.
_MIN_CURVE_POINTS = 48


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
        if kind == "circle":
            CircleGeometryBlockSpec.model_validate(data)
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


def _is_point_marker(spec: GraphBlockSpec) -> bool:
    """True for coordinate markers / discrete points — never densify those
    into a continuous curve."""
    if spec.type == "vertical":
        return True
    if len(spec.points) <= 1:
        return True
    if len(spec.points) >= 2 and len({float(p[0]) for p in spec.points}) == 1:
        # All x's identical — vertical segment, not y=f(x).
        return True
    if spec.expr.strip().startswith("("):
        return True
    title = (spec.title or "").strip().lower()
    return title.startswith("point")


def _sample_domain(spec: GraphBlockSpec) -> tuple[float, float]:
    xs = [float(p[0]) for p in spec.points]
    span_min, span_max = min(xs), max(xs)
    declared_min, declared_max = float(spec.x_min), float(spec.x_max)
    if declared_max > declared_min and (
        declared_min < span_min - 1e-9 or declared_max > span_max + 1e-9
    ):
        # Model declared a wider plotting window than the handful of key
        # points it listed (common: roots only, domain still [-10, 10]).
        return declared_min, declared_max
    if span_max <= span_min:
        return span_min - 1.0, span_max + 1.0
    pad = max(1.0, (span_max - span_min) * 0.25)
    return span_min - pad, span_max + pad


def densify_sparse_graph(spec: GraphBlockSpec) -> GraphBlockSpec:
    """Re-sample a sparse continuous function fence so the client draws a
    smooth curve instead of a few straight segments."""
    if spec.type == "vertical" or _is_point_marker(spec) or len(spec.points) >= _MIN_CURVE_POINTS:
        return spec
    if "=" in spec.expr and not spec.expr.strip().lower().startswith((spec.variable + "=", "y=")):
        # Vertical / relation forms like "x = 4" cannot be sampled as y=f(x).
        return spec
    x_min, x_max = _sample_domain(spec)
    settings = get_settings()
    try:
        sample = math_service.sample_function(
            GraphSampleInput(
                expr=spec.expr[: settings.math_max_expr_length],
                variable=spec.variable,
                x_min=x_min,
                x_max=x_max,
                n=settings.math_graph_max_points,
            )
        )
    except (MathServiceError, ValueError, TypeError):
        return spec
    if len(sample.points) < 2:
        return spec
    has_discontinuity = len(sample.segments) > 1
    return GraphBlockSpec(
        type="function",
        expr=sample.expr,
        variable=sample.variable,
        x_min=sample.x_min,
        x_max=sample.x_max,
        title=spec.title,
        points=sample.points,
        segments=sample.segments if has_discontinuity else [],
    )


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
            return match.group(0)
        parsed = GraphBlockSpec.model_validate(json.loads(raw))
        densified = densify_sparse_graph(parsed)
        # Preserve the model's original fence text when we did not re-sample
        # (point markers / already-dense curves) so we don't churn formatting.
        if densified is parsed:
            return match.group(0)
        return f"```graph\n{json.dumps(densified.model_dump(), separators=(',', ':'))}\n```"
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        # Soft prose — never a CopyBlock / code fence. Callouts got routed
        # into copyable cards for short meta lines; keep math failures quiet.
        return "\n*Could not render that diagram.*\n"


def validate_math_fences(content: str, *, verified: VerifiedMathBlock | None = None) -> str:
    canonical_fence = verified.canonical_fence if verified is not None else None
    content = _GEOMETRY_FENCE.sub(lambda m: _replace_fence(m, "geometry", canonical_fence), content)
    return _GRAPH_FENCE.sub(lambda m: _replace_fence(m, "graph", canonical_fence), content)
