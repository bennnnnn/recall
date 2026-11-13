"""Which verified fence of the turn stands in for a solver-owned fence the model wrote.

``math.fence`` rewrites the model's ```geometry and ```graph fences to the turn's canonical
ones; this matches them: by type and shape, a graph step to the verified number line, and
failing those, for a fence naming no shape of its own, the turn's verified picture of the
same kind. A fence naming a shape the turn did not draw has no stand-in, and goes.
"""

from __future__ import annotations

import json

_GEOMETRY_TYPES = frozenset(
    {
        "rectangle",
        "rect",
        "square",
        "triangle",
        "right_triangle",
        "triangle_sides",
        "circle",
        "trapezoid",
        "parallelogram",
        "sector",
    }
)
_GRAPH_TYPES = frozenset({"function", "vertical", "number_line", "trajectory", "inequality"})
_ALIASES = {"rect": "rectangle", "trapezoid": "trapezium"}
# Shapes a model's fence may name: one of these that the turn did not draw is dropped.
_KNOWN = (_GEOMETRY_TYPES | _GRAPH_TYPES | {"points", "trapezium", "rhombus", "kite"}) - {"rect"}


def canonical_replacement(
    raw: str,
    canonical_fence: dict[str, object] | None,
    canonical_fences: list[dict[str, object]] | None = None,
    label: str | None = None,
) -> str | None:
    """If a canonical fence exists for this turn and the model's fence is the
    same kind, return the canonical JSON to substitute in — the model's own
    numbers are never trusted once we have the real computed values.

    ``canonical_fences`` (from multiple tool-loop rounds) is matched by type
    so a geometry fence from round 1 isn't lost when round 2 produced a graph
    fence. The primary is searched **alongside** it, not only when it is empty:
    the other two readers of this pair (`collect_canonical_specs` and
    `_solver_fences`) already prepend the primary, and this one treating the
    list as a replacement meant a caller storing only the extras would have its
    primary silently stop matching — which is exactly what happened when a
    physics scene was added beside a trajectory graph, striking out the graph
    the reply already carried. The tool loop stores the primary in both, and a
    duplicate here is harmless: the first type match wins either way.
    """
    fences = [fence for fence in (canonical_fence, *(canonical_fences or [])) if fence is not None]
    if not fences:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return _same_kind(fences, label)
    data_type = data.get("type")
    for fence in fences:
        if data_type == fence.get("type") and _shape(data) in {None, _shape(fence)}:
            return json.dumps(fence, separators=(",", ":"))
    # Model often emits a y=f(x) step for "graph x > 3"; replace any graph
    # fence with the verified number line.
    for fence in fences:
        if fence.get("type") == "inequality" and data_type in _GRAPH_TYPES:
            return json.dumps(fence, separators=(",", ":"))
        if fence.get("type") == "number_line" and data_type in {
            "function",
            "vertical",
            "number_line",
        }:
            return json.dumps(fence, separators=(",", ":"))
        if fence.get("type") == "trajectory" and data_type in {
            "function",
            "vertical",
            "trajectory",
        }:
            return json.dumps(fence, separators=(",", ":"))
    for fence in fences:
        if _shape(data) is not None and _shape(fence) == _shape(data):
            return json.dumps(fence, separators=(",", ":"))  # a rectangle the server drew
    if _shape(data) in _KNOWN:
        # The model drew a shape of its own ("circle" on a turn that drew a rectangle):
        # no picture of the turn stands in for it.
        return None
    return _same_kind(fences, label)


def _shape(spec: dict[str, object]) -> str | None:
    """The shape a fence draws: its type, or a figure's shape ("rectangle", "circle_square")."""
    name = spec.get("shape") if spec.get("type") == "figure" else spec.get("type")
    if not isinstance(name, str):
        return None
    # A triangle by its sides, a right one, an isosceles one: all a triangle.
    return (
        "triangle"
        if name.endswith("triangle") or name == "triangle_sides"
        else (_ALIASES.get(name, name))
    )


def _same_kind(fences: list[dict[str, object]], label: str | None) -> str | None:
    """The turn's verified picture of the fence's kind, when the model's own names no shape:
    a ```graph the model typed "line" (or wrote unreadably) on a turn that drew y = 2x + 1
    is that graph, in the model's place. A fence naming another shape is never matched
    here: a rectangle stood in for a model's circle, under the circle's caption."""
    if label is None:
        return None
    for fence in fences:
        if spec_fence_kind(fence) == label:
            return json.dumps(fence, separators=(",", ":"))
    return None


def spec_fence_kind(spec: dict[str, object]) -> str | None:
    from app.modules.math.schemas.teaching import TEACHING_TYPES

    spec_type = spec.get("type")
    if spec_type == "answer":
        return "answer"
    if spec_type in TEACHING_TYPES:
        return "teach"
    if spec_type == "arithmetic":
        return "arithmetic"
    if spec_type == "fraction":
        return "arithmetic"
    if spec_type in _GEOMETRY_TYPES:
        return "geometry"
    if spec_type in _GRAPH_TYPES:
        return "graph"
    if any(key in spec for key in ("width", "height", "side", "radius", "base", "top")):
        return "geometry"
    if any(key in spec for key in ("expr", "points", "x_min", "intervals")):
        return "graph"
    return None
