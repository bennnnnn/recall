"""Validate geometry/graph/answer fences in assistant output.

The model is asked to explain in Markdown + ``$...$``. Recall attaches
solver-owned `` ```answer `` / `` ```graph `` / `` ```geometry `` after the
stream from ``VerifiedMathBlock``. If the model still emitted a same-kind
fence, it is replaced with the canonical JSON (or answer body) so a
drifted or hallucinated number never reaches the user.

When this turn produced a canonical `` ```graph `` fence but it (or the
substituted JSON) is still sparse, we densify by re-sampling that *verified*
expression. Sparse *unverified* y=f(x) fences are also resampled from the
fence's own ``expr`` — otherwise the client draws a 3-point polyline (a V
for a parabola). Discrete point markers and vertical lines stay untouched.

After rewriting any fences the model still produced, we append canonical
fences that are missing so the client always gets the solver-owned
diagram. An `` ```answer `` pill is appended only when the verified
value is not already stated in the prose (so a one-line ``$3+0=3$`` is
not duplicated as a result card).
"""

from __future__ import annotations

import json
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
from app.services.md_fence_scan import (
    find_lang_opener,
    has_closed_fence,
    is_fence_closer,
    map_closed_fences,
    next_fence_marker_line,
)

if TYPE_CHECKING:
    from app.services.math_tools import VerifiedMathBlock

# Below this count a continuous y=f(x) fence is treated as "sparse key points"
# the model listed for prose, not a renderable curve sample.
_MIN_CURVE_POINTS = 48
# Shared 5s SymPy budget for the whole reply — bound how many fences we
# rewrite so one long message degrades per-fence instead of timing out all.
_MAX_ANSWER_FENCES = 4
_MAX_GEOMETRY_FENCES = 4
_MAX_GRAPH_FENCES = 2

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
_GRAPH_TYPES = frozenset({"function", "vertical", "number_line", "trajectory"})


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


def _canonical_replacement(
    raw: str,
    canonical_fence: dict[str, object] | None,
    canonical_fences: list[dict[str, object]] | None = None,
) -> str | None:
    """If a canonical fence exists for this turn and the model's fence is the
    same kind, return the canonical JSON to substitute in — the model's own
    numbers are never trusted once we have the real computed values.

    ``canonical_fences`` (from multiple tool-loop rounds) is matched by type
    so a geometry fence from round 1 isn't lost when round 2 produced a graph
    fence. Falls back to the single ``canonical_fence`` for backward compat.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    fences = canonical_fences or ([canonical_fence] if canonical_fence is not None else [])
    if not fences:
        return None
    data_type = data.get("type")
    for fence in fences:
        if data_type == fence.get("type"):
            return json.dumps(fence, separators=(",", ":"))
    # Model often emits a y=f(x) step for "graph x > 3"; replace any graph
    # fence with the verified number line.
    for fence in fences:
        if fence.get("type") == "number_line" and data_type in {
            "function",
            "vertical",
            "number_line",
        }:
            return json.dumps(fence, separators=(",", ":"))
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
    if spec.type in {"vertical", "number_line", "trajectory"} or _is_point_marker(spec):
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
    if spec.type in {"number_line", "vertical", "trajectory"}:
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


def _replace_unclosed_graph_fence(
    content: str,
    canonical_fence: dict[str, object] | None,
    *,
    densify: bool = True,
) -> str:
    """Replace a ```graph fence the model left unclosed (truncated mid-JSON,
    usually because it stopped copying the verified points array at EOS).

    Closed fences are handled separately. This only fires when the next
    fence marker is another opener (```python) or the message ends — so
    following prose is not swallowed into the graph body.
    """
    opener = find_lang_opener(content, "graph")
    while opener is not None:
        newline = content.find("\n", opener)
        if newline < 0:
            head, rest = content[:opener], ""
            break
        marker = next_fence_marker_line(content, newline + 1)
        if marker is None:
            head, rest = content[:opener], ""
            break
        line_start, after, stripped = marker
        if is_fence_closer(stripped):
            opener = find_lang_opener(content, "graph", after)
            continue
        head, rest = content[:opener], content[line_start:]
        break
    else:
        return content

    if canonical_fence is None or canonical_fence.get("type") not in {
        "function",
        "vertical",
        "number_line",
        "trajectory",
    }:
        note = "\n*Could not render that diagram.*\n"
        return head + note + rest
    try:
        parsed = GraphBlockSpec.model_validate(canonical_fence)
    except (ValidationError, TypeError):
        note = "\n*Could not render that diagram.*\n"
        return head + note + rest
    spec = densify_sparse_graph(parsed) if densify else parsed
    suffix = rest if rest.startswith("\n") else ("\n" + rest if rest else "\n")
    return head + "\n" + _graph_fence_body(spec) + suffix


def replace_unclosed_graph_fence_safe(
    content: str, canonical_fence: dict[str, object] | None
) -> str:
    """SymPy-free fallback for an unclosed ```graph fence.

    Use on the ``validate_math_fences`` timeout path: the densify pass (which
    runs SymPy) was killed, but a truncated graph fence the model left at EOS
    still needs to be cleaned up so the client doesn't render a half-pasted
    points array. Substitute the verified canonical fence as-is or strip to the
    "Could not render that diagram." note. No SymPy, no sampling — safe to
    run after a solve timeout.
    """
    return _replace_unclosed_graph_fence(content, canonical_fence, densify=False)


def _sample_function_graph_from_json(raw: str) -> GraphBlockSpec | None:
    """Build a sampled function graph from a fence that has ``expr`` but
    failed schema (usually empty/missing ``points``).

    The model is prompted to emit ```graph for y=f(x) even when this turn
    had no verified sample. That JSON typically copies the schema example
    without a points array — validation then strips it to
    "Could not render that diagram." Sampling here recovers the plot.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    gtype = data.get("type", "function")
    if gtype not in (None, "function"):
        return None
    expr = data.get("expr")
    if not isinstance(expr, str) or not expr.strip():
        return None
    expr = _strip_y_equals(expr)
    if not expr:
        return None
    variable = data.get("variable")
    if not isinstance(variable, str) or not variable.strip():
        variable = "x"
    try:
        x_min = float(data["x_min"]) if data.get("x_min") is not None else -10.0
        x_max = float(data["x_max"]) if data.get("x_max") is not None else 10.0
    except (TypeError, ValueError):
        x_min, x_max = -10.0, 10.0
    if x_max <= x_min:
        x_min, x_max = -10.0, 10.0
    settings = get_settings()
    sampled = _resample_curve(
        expr,
        variable.strip(),
        x_min,
        x_max,
        settings.math_graph_max_points,
        settings.math_max_expr_length,
    )
    if sampled is None:
        return None
    points, segments, expr_out, var_out, out_xmin, out_xmax = sampled
    title = data.get("title")
    try:
        return GraphBlockSpec(
            type="function",
            expr=expr_out,
            variable=var_out,
            x_min=out_xmin,
            x_max=out_xmax,
            title=title if isinstance(title, str) else None,
            points=points,
            segments=segments,
        )
    except ValidationError:
        return None


def _replace_fence(
    raw: str,
    label: str,
    original: str,
    canonical_fence: dict[str, object] | None,
    canonical_fences: list[dict[str, object]] | None = None,
) -> str:
    raw = raw.strip()
    corrected = _canonical_replacement(raw, canonical_fence, canonical_fences)
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
            return original
        parsed = GraphBlockSpec.model_validate(json.loads(raw))
        rewritten = _rewrite_inequality_graph(parsed)
        if rewritten is not parsed:
            return _graph_fence_body(rewritten)
        densified = densify_sparse_graph(parsed)
        if densified is parsed:
            return original
        return _graph_fence_body(densified)
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        if label == "graph":
            recovered = _sample_function_graph_from_json(raw)
            if recovered is not None:
                return _graph_fence_body(recovered)
        # Soft prose — never a CopyBlock / code fence. Callouts got routed
        # into copyable cards for short meta lines; keep math failures quiet.
        return "\n*Could not render that diagram.*\n"


def _canonical_answer_body(verified: VerifiedMathBlock | None) -> str | None:
    if verified is None:
        return None
    if verified.canonical_answer and verified.canonical_answer.strip():
        return verified.canonical_answer.strip()
    fences: list[dict[str, object]] = []
    if verified.canonical_fence:
        fences.append(verified.canonical_fence)
    fences.extend(verified.canonical_fences or [])
    for fence in fences:
        if fence.get("type") != "answer":
            continue
        content = fence.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _spec_fence_kind(spec: dict[str, object]) -> str | None:
    spec_type = spec.get("type")
    if spec_type == "answer":
        return "answer"
    if spec_type in _GEOMETRY_TYPES:
        return "geometry"
    if spec_type in _GRAPH_TYPES:
        return "graph"
    if any(key in spec for key in ("width", "height", "side", "radius", "base", "top")):
        return "geometry"
    if any(key in spec for key in ("expr", "points", "x_min", "intervals")):
        return "graph"
    return None


def _markdown_fence(kind: str, body: str) -> str:
    return f"```{kind}\n{body}\n```"


def _collect_canonical_specs(verified: VerifiedMathBlock) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    seen: set[int] = set()
    for spec in [verified.canonical_fence, *(verified.canonical_fences or [])]:
        if not isinstance(spec, dict):
            continue
        marker = id(spec)
        if marker in seen:
            continue
        seen.add(marker)
        specs.append(spec)
    return specs


def _normalize_answer_token(text: str) -> str:
    """Strip math/markup noise so we can test whether prose already states a value."""
    cleaned = (
        text.replace("$", "")
        .replace("`", "")
        .replace("\u2009", "")
        .replace("\u00a0", "")
        .replace("\u2212", "-")
        .replace("\\", "")
    )
    return "".join(cleaned.split()).lower()


def _answer_numeric_core(answer_body: str) -> str:
    """Strip a leading ``x=`` and trailing latin unit so ``2.02 s`` → ``2.02``."""
    token = _normalize_answer_token(answer_body)
    equals = token.rfind("=")
    if equals >= 0:
        token = token[equals + 1 :]
    end = len(token)
    while end > 0 and token[end - 1].isalpha():
        end -= 1
    return token[:end]


def _math_spans(prose: str) -> list[str]:
    """Return bodies of ``$...$`` spans using linear ``find`` (no nested regex)."""
    spans: list[str] = []
    index = 0
    while True:
        start = prose.find("$", index)
        if start < 0:
            break
        end = prose.find("$", start + 1)
        if end < 0:
            break
        spans.append(prose[start + 1 : end])
        index = end + 1
    return spans


def _span_states_short_int(span: str, core: str) -> bool:
    compact = _normalize_answer_token(span)
    return compact == core or compact.endswith("=" + core)


def _prose_already_states_answer(content: str, answer_body: str) -> bool:
    """True when the verified value is already visible in the assistant prose.

    Short integers (1-2 digits) must appear as a whole math result (``$2$`` or
    a span ending in ``=2``) so a digit inside ``$x^2$`` does not suppress the
    pill. Longer values (``2.02 s``, ``x = 12``) use a normalized substring.
    """
    body = answer_body.strip()
    if not body:
        return False
    core = _answer_numeric_core(body)
    if core.isdigit() and len(core) <= 2:
        return any(_span_states_short_int(span, core) for span in _math_spans(content))
    needle = _normalize_answer_token(body)
    if len(needle) < 2:
        return False
    return needle in _normalize_answer_token(content)


def _append_missing_canonical_fences(content: str, verified: VerifiedMathBlock | None) -> str:
    """Attach solver-owned fences the model was told not to emit."""
    if verified is None:
        return content
    extras: list[str] = []
    answer_body = _canonical_answer_body(verified)
    if (
        answer_body
        and not has_closed_fence(content, "answer")
        and not _prose_already_states_answer(content, answer_body)
    ):
        extras.append(_markdown_fence("answer", answer_body))

    specs = _collect_canonical_specs(verified)
    geo = next((spec for spec in specs if _spec_fence_kind(spec) == "geometry"), None)
    if geo is not None and not has_closed_fence(content, "geometry"):
        extras.append(_markdown_fence("geometry", json.dumps(geo, separators=(",", ":"))))
    graph = next((spec for spec in specs if _spec_fence_kind(spec) == "graph"), None)
    if graph is not None and not has_closed_fence(content, "graph"):
        extras.append(_markdown_fence("graph", json.dumps(graph, separators=(",", ":"))))

    if not extras:
        return content
    stripped = content.rstrip()
    if stripped:
        return stripped + "\n\n" + "\n\n".join(extras) + "\n"
    return "\n\n".join(extras) + "\n"


def _replace_answer_fence(raw: str, original: str, answer_body: str | None) -> str:
    """Rewrite ```answer bodies from SymPy when this turn computed one."""
    if not answer_body:
        return original
    return f"```answer\n{answer_body}\n```"


def _strip_y_equals(expr: str) -> str:
    """``y = x/2`` → ``x/2`` so sample_function (which expects y=f(x)) can plot it."""
    e = expr.strip()
    low = e.lower()
    if low.startswith("y="):
        return e[2:].strip()
    if low.startswith("y ="):
        return e[3:].strip()
    return e


def _function_call_json_to_graph_fence(raw: str) -> str:
    """Turn one ``!function_call:{...}`` JSON blob into a ```graph fence, or "".

    Some models emit a tool call as text instead of via the structured
    ``tool_calls`` API. For a ``graph`` call we sample the expr server-side
    (reusing the same densify helper) so the renderer gets a real curve;
    any other call (or a bad graph expr) is stripped so the raw
    ``!function_call:...`` text never reaches the user.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    call = str(data.get("call") or data.get("name") or "")
    args = data.get("arguments")
    if not isinstance(args, dict):
        args = {}
    if call != "graph":
        return ""
    expr = _strip_y_equals(str(args.get("expr") or ""))
    if not expr:
        return ""
    variable = str(args.get("variable") or "x")
    try:
        x_min = float(args.get("x_min") or -10.0)
        x_max = float(args.get("x_max") or 10.0)
    except (TypeError, ValueError):
        x_min, x_max = -10.0, 10.0
    settings = get_settings()
    sampled = _resample_curve(
        expr,
        variable,
        x_min,
        x_max,
        settings.math_graph_max_points,
        settings.math_max_expr_length,
    )
    if sampled is None:
        return ""
    points, segments, s_expr, s_var, s_xmin, s_xmax = sampled
    spec = GraphBlockSpec(
        expr=s_expr,
        variable=s_var,
        x_min=s_xmin,
        x_max=s_xmax,
        points=points,
        segments=segments,
    )
    return _graph_fence_body(spec)


def convert_function_call_text(content: str) -> str:
    """Find ``!function_call:{...}`` blobs (balanced JSON, may span lines) and
    replace each with a ```graph fence (for graph calls) or strip it."""
    marker = "!function_call:"
    out: list[str] = []
    i = 0
    while True:
        idx = content.find(marker, i)
        if idx == -1:
            out.append(content[i:])
            break
        out.append(content[i:idx])
        start = content.find("{", idx)
        if start == -1:
            i = len(content)
            break
        depth = 0
        end = start
        in_str = False
        esc = False
        for j in range(start, len(content)):
            ch = content[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
        raw = content[start:end]
        out.append(_function_call_json_to_graph_fence(raw))
        i = end
    return "".join(out)


def validate_math_fences(content: str, *, verified: VerifiedMathBlock | None = None) -> str:
    canonical_fence = verified.canonical_fence if verified is not None else None
    canonical_fences = verified.canonical_fences if verified is not None else []
    answer_body = _canonical_answer_body(verified)
    # Models sometimes emit a tool call as text (!function_call:{...}) instead
    # of the structured tool_calls API — convert graph calls to real fences and
    # strip the rest before fence validation runs.
    content = convert_function_call_text(content)
    content = map_closed_fences(
        content,
        "answer",
        lambda body: _replace_answer_fence(body, f"```answer\n{body}```", answer_body),
        max_count=_MAX_ANSWER_FENCES,
    )
    content = map_closed_fences(
        content,
        "geometry",
        lambda body: _replace_fence(
            body,
            "geometry",
            f"```geometry\n{body}```",
            canonical_fence,
            canonical_fences,
        ),
        max_count=_MAX_GEOMETRY_FENCES,
    )
    content = map_closed_fences(
        content,
        "graph",
        lambda body: _replace_fence(
            body,
            "graph",
            f"```graph\n{body}```",
            canonical_fence,
            canonical_fences,
        ),
        max_count=_MAX_GRAPH_FENCES,
    )
    # A ```graph fence the model truncated mid-JSON (stopped copying the
    # verified points at EOS) is left unclosed. Swap it for the verified
    # canonical fence so the renderer gets a complete spec.
    content = _replace_unclosed_graph_fence(content, canonical_fence)
    return _append_missing_canonical_fences(content, verified)


def validate_math_fences_worker(content: str, verified: VerifiedMathBlock | None = None) -> str:
    """Picklable entry for ``sympy_executor.run_sympy`` (positional args only)."""
    return validate_math_fences(content, verified=verified)
