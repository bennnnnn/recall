"""Validate geometry/graph/answer fences in assistant output.

Schema validity alone doesn't mean the *numbers* are right — the model is
only asked (in the system prompt) to copy the SymPy-computed fence
verbatim, not structurally forced to. When the turn actually computed a
canonical fence (``VerifiedMathBlock.canonical_fence``), a same-kind fence
in the model's output is replaced with the canonical JSON (or answer
body) outright, so a drifted or hallucinated number never reaches the
user even inside an otherwise schema-valid block.

When this turn produced a canonical `` ```graph `` fence but it (or the
substituted JSON) is still sparse, we densify by re-sampling that *verified*
expression. Sparse *unverified* y=f(x) fences are also resampled from the
fence's own ``expr`` — otherwise the client draws a 3-point polyline (a V
for a parabola). Discrete point markers and vertical lines stay untouched.
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
    ParallelogramGeometryBlockSpec,
    RightTriangleGeometryBlockSpec,
    SectorGeometryBlockSpec,
    TrapezoidGeometryBlockSpec,
    TriangleGeometryBlockSpec,
    TriangleSidesGeometryBlockSpec,
)
from app.services import math_service
from app.services.math_service import MathServiceError

if TYPE_CHECKING:
    from app.services.math_tools import VerifiedMathBlock

_GEOMETRY_FENCE = re.compile(r"```geometry\s*\n([\s\S]*?)```", re.IGNORECASE)
_GRAPH_FENCE = re.compile(r"```graph\s*\n([\s\S]*?)```", re.IGNORECASE)
_ANSWER_FENCE = re.compile(r"```(?:answer|result|final)\s*\n([\s\S]*?)```", re.IGNORECASE)

# Below this count a continuous y=f(x) fence is treated as "sparse key points"
# the model listed for prose, not a renderable curve sample.
_MIN_CURVE_POINTS = 48
# Shared 5s SymPy budget for the whole reply — bound how many fences we
# rewrite so one long message degrades per-fence instead of timing out all.
_MAX_ANSWER_FENCES = 4
_MAX_GEOMETRY_FENCES = 4
_MAX_GRAPH_FENCES = 2


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
        if kind == "triangle_sides":
            TriangleSidesGeometryBlockSpec.model_validate(data)
            return True
        if kind == "trapezoid":
            TrapezoidGeometryBlockSpec.model_validate(data)
            return True
        if kind == "parallelogram":
            ParallelogramGeometryBlockSpec.model_validate(data)
            return True
        if kind == "sector":
            SectorGeometryBlockSpec.model_validate(data)
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
    if not isinstance(data, dict):
        return None
    if data.get("type") == canonical_fence.get("type"):
        return json.dumps(canonical_fence, separators=(",", ":"))
    # Model often emits a y=f(x) step for "graph x > 3"; replace any graph
    # fence with the verified number line.
    if canonical_fence.get("type") == "number_line" and data.get("type") in {
        "function",
        "vertical",
        "number_line",
    }:
        return json.dumps(canonical_fence, separators=(",", ":"))
    return None


def _is_point_marker(spec: GraphBlockSpec) -> bool:
    """True for coordinate markers / discrete points — never densify those
    into a continuous curve."""
    if spec.type in {"vertical", "number_line"}:
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
    """Choose a densify window from key points union declared x_min/x_max.

    Take the span covering both (not "declared wins when wider") so
    off-window roots/extrema in ``points`` still expand a default
    [-10, 10] declaration, and a wider declared domain still covers
    sparse root-only point lists.
    """
    xs = [float(p[0]) for p in spec.points]
    if spec.points2:
        xs.extend(float(p[0]) for p in spec.points2)
    span_min, span_max = min(xs), max(xs)
    declared_min, declared_max = float(spec.x_min), float(spec.x_max)
    if declared_max > declared_min:
        span_min = min(span_min, declared_min)
        span_max = max(span_max, declared_max)
    if span_max <= span_min:
        return span_min - 1.0, span_max + 1.0
    pad = max(1.0, (span_max - span_min) * 0.25)
    return span_min - pad, span_max + pad


def _expr_samplable_as_function(expr: str, variable: str) -> bool:
    """False for relation forms like ``x = 4`` that aren't y=f(x)."""
    e = expr.strip().lower()
    if "=" in expr and not e.startswith((variable.lower() + "=", "y=")):
        return False
    if any(op in expr for op in (">", "<", "≥", "≤")):
        return False
    return True


def _curve_needs_densify(
    points: list[list[float]] | None,
    expr: str | None,
    variable: str,
) -> bool:
    if not expr or not points or len(points) < 2:
        return False
    if len(points) >= _MIN_CURVE_POINTS:
        return False
    return _expr_samplable_as_function(expr, variable)


def _resample_curve(
    expr: str,
    variable: str,
    x_min: float,
    x_max: float,
    n: int,
    max_expr_length: int,
) -> tuple[list[list[float]], list[list[list[float]]], str, str, float, float] | None:
    try:
        sample = math_service.sample_function(
            GraphSampleInput(
                expr=expr[:max_expr_length],
                variable=variable,
                x_min=x_min,
                x_max=x_max,
                n=n,
            )
        )
    except (MathServiceError, ValueError, TypeError):
        return None
    if len(sample.points) < 2:
        return None
    segments = sample.segments if len(sample.segments) > 1 else []
    return (
        sample.points,
        segments,
        sample.expr,
        sample.variable,
        sample.x_min,
        sample.x_max,
    )


def densify_sparse_graph(spec: GraphBlockSpec) -> GraphBlockSpec:
    """Re-sample sparse continuous curve(s) so the client draws smooth plots.

    Densifies curve 1 and curve 2 independently — previously an early return
    when curve 1 was already dense left a sparse ``points2`` as a jagged
    polyline, and densifying curve 1 preserved but never resampled curve 2.
    """
    if spec.type in {"vertical", "number_line"} or _is_point_marker(spec):
        return spec

    var2 = (spec.variable2 or spec.variable).strip() or "x"
    needs1 = _curve_needs_densify(spec.points, spec.expr, spec.variable)
    needs2 = _curve_needs_densify(spec.points2, spec.expr2, var2)
    if not needs1 and not needs2:
        return spec

    x_min, x_max = _sample_domain(spec)
    settings = get_settings()
    n = settings.math_graph_max_points
    max_len = settings.math_max_expr_length

    points = spec.points
    segments = spec.segments or []
    expr = spec.expr
    variable = spec.variable
    out_x_min, out_x_max = float(spec.x_min), float(spec.x_max)

    if needs1:
        sampled = _resample_curve(spec.expr, spec.variable, x_min, x_max, n, max_len)
        if sampled is not None:
            points, segments, expr, variable, out_x_min, out_x_max = sampled

    points2 = spec.points2
    segments2 = spec.segments2
    if needs2 and spec.expr2:
        sampled2 = _resample_curve(spec.expr2, var2, x_min, x_max, n, max_len)
        if sampled2 is not None:
            points2, segments2, _, _, _, _ = sampled2

    if points is spec.points and points2 is spec.points2:
        return spec

    return GraphBlockSpec(
        type="function",
        expr=expr,
        variable=variable,
        x_min=out_x_min,
        x_max=out_x_max,
        title=spec.title,
        points=points,
        segments=segments,
        expr2=spec.expr2,
        variable2=spec.variable2,
        points2=points2,
        segments2=segments2,
        label=spec.label,
        label2=spec.label2,
    )


def _rewrite_inequality_graph(spec: GraphBlockSpec) -> GraphBlockSpec:
    """Turn a y=f(x) fence whose expr is ``x > 3`` into a number line.

    The model (and an older sample_function path) plotted inequalities as a
    0/1 step. School graphs of ``x > 3`` are a number line, not a Heaviside.
    """
    if spec.type in {"number_line", "vertical"}:
        return spec
    line = math_service.number_line_spec_from_expr(spec.expr, spec.variable)
    if line is None:
        return spec
    title = (spec.title or "").strip()
    if title:
        return line.model_copy(update={"title": title[:64]})
    return line


def _graph_fence_body(spec: GraphBlockSpec) -> str:
    return f"```graph\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"


def _replace_fence(
    match: re.Match[str],
    label: str,
    canonical_fence: dict[str, object] | None,
) -> str:
    raw = match.group(1).strip()
    corrected = _canonical_replacement(raw, canonical_fence)
    if corrected is not None:
        if label != "graph":
            return f"```{label}\n{corrected}\n```"
        # Densify only the verified canonical curve — never an unverified
        # model expr (that would polish a wrong function into looking true).
        try:
            parsed = GraphBlockSpec.model_validate(json.loads(corrected))
        except (json.JSONDecodeError, ValidationError, TypeError):
            return f"```{label}\n{corrected}\n```"
        densified = densify_sparse_graph(parsed)
        if densified is parsed:
            return f"```graph\n{corrected}\n```"
        return _graph_fence_body(densified)
    try:
        if label == "geometry":
            if not _validate_geometry(raw):
                raise ValueError("invalid geometry")
            return match.group(0)
        parsed = GraphBlockSpec.model_validate(json.loads(raw))
        rewritten = _rewrite_inequality_graph(parsed)
        if rewritten is not parsed:
            return _graph_fence_body(rewritten)
        densified = densify_sparse_graph(parsed)
        if densified is parsed:
            return match.group(0)
        return _graph_fence_body(densified)
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        # Soft prose — never a CopyBlock / code fence. Callouts got routed
        # into copyable cards for short meta lines; keep math failures quiet.
        return "\n*Could not render that diagram.*\n"


def _replace_answer_fence(
    match: re.Match[str],
    canonical_fence: dict[str, object] | None,
) -> str:
    """Rewrite ```answer bodies from SymPy when this turn computed one."""
    if canonical_fence is None or canonical_fence.get("type") != "answer":
        return match.group(0)
    content = canonical_fence.get("content")
    if not isinstance(content, str) or not content.strip():
        return match.group(0)
    return f"```answer\n{content.strip()}\n```"


def validate_math_fences(content: str, *, verified: VerifiedMathBlock | None = None) -> str:
    canonical_fence = verified.canonical_fence if verified is not None else None
    content = _ANSWER_FENCE.sub(
        lambda m: _replace_answer_fence(m, canonical_fence),
        content,
        count=_MAX_ANSWER_FENCES,
    )
    content = _GEOMETRY_FENCE.sub(
        lambda m: _replace_fence(m, "geometry", canonical_fence),
        content,
        count=_MAX_GEOMETRY_FENCES,
    )
    return _GRAPH_FENCE.sub(
        lambda m: _replace_fence(m, "graph", canonical_fence),
        content,
        count=_MAX_GRAPH_FENCES,
    )


def validate_math_fences_worker(content: str, verified: VerifiedMathBlock | None = None) -> str:
    """Picklable entry for ``sympy_executor.run_sympy`` (positional args only)."""
    return validate_math_fences(content, verified=verified)
