"""Validate geometry/graph/answer fences in assistant output.

The model is asked to explain in Markdown + ``$...$``. Recall attaches
solver-owned `` ```answer `` / `` ```graph `` / `` ```geometry `` after the
stream from ``VerifiedMathBlock``. If the model still emitted a same-kind
fence, it is replaced with the canonical JSON (or answer body) so a
drifted or hallucinated number never reaches the user.

When this turn produced a canonical `` ```graph `` fence but it (or the
substituted JSON) is still sparse, we densify by re-sampling that *verified*
expression. Model-emitted geometry/graph JSON with no matching canonical
fence is stripped — schema-valid invented numbers must not ship as if
verified. Discrete point markers and vertical lines stay untouched.

After rewriting any fences the model still produced, we append canonical
fences that are missing so the client always gets the solver-owned
diagram. An `` ```answer `` pill is appended only when the verified
value is not already stated in the prose (so a one-line ``$3+0=3$`` is
not duplicated as a result card).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schemas.math import (
    GraphBlockSpec,
    GraphSampleInput,
)
from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.modules.math import solve as math_solve
from app.modules.math.solve import MathServiceError
from app.services.md_fence_scan import (
    find_lang_opener,
    has_closed_fence,
    is_fence_closer,
    map_closed_fences,
    next_fence_marker_line,
    strip_closed_fences,
    strip_gfm_pipe_tables,
    strip_hand_sketch_filler,
)

if TYPE_CHECKING:
    from app.modules.math.tools import VerifiedMathBlock

logger = logging.getLogger(__name__)

# Below this count a continuous y=f(x) fence is treated as "sparse key points"
# the model listed for prose, not a renderable curve sample.
_MIN_CURVE_POINTS = 48
# Shared 5s SymPy budget for the whole reply — bound how many fences we
# rewrite so one long message degrades per-fence instead of timing out all.
_MAX_ANSWER_FENCES = 4
_MAX_GEOMETRY_FENCES = 4
_MAX_GRAPH_FENCES = 2
# One scene per answer. Unlike geometry, there is no question whose answer is
# two animations.
_MAX_SIMULATION_FENCES = 1
_ANSWER_FENCE_LANGS = ("answer", "result", "final")
_CHART_ALIAS_LANGS = ("chart", "vega", "vega-lite", "plot")
_DIAGRAM_FAIL_NOTE = "\n*Could not render that diagram.*\n"

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
    fence. The primary is searched **alongside** it, not only when it is empty:
    the other two readers of this pair (`_collect_canonical_specs` and
    `_solver_fences`) already prepend the primary, and this one treating the
    list as a replacement meant a caller storing only the extras would have its
    primary silently stop matching — which is exactly what happened when a
    physics scene was added beside a trajectory graph, striking out the graph
    the reply already carried. The tool loop stores the primary in both, and a
    duplicate here is harmless: the first type match wins either way.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    fences = [fence for fence in (canonical_fence, *(canonical_fences or [])) if fence is not None]
    if not fences:
        return None
    data_type = data.get("type")
    for fence in fences:
        if data_type == fence.get("type"):
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
        sample = math_solve.sample_function(
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
    if spec.type in {"vertical", "number_line", "trajectory", "inequality"} or _is_point_marker(
        spec
    ):
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
        "inequality",
    }:
        note = _DIAGRAM_FAIL_NOTE
        return head + note + rest
    try:
        parsed = GraphBlockSpec.model_validate(canonical_fence)
    except (ValidationError, TypeError):
        note = _DIAGRAM_FAIL_NOTE
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
    points array. Closed unmatched `` ```geometry `` / `` ```graph `` fences
    are degraded the same way as ``validate_math_fences`` (P0-G), without
    densify. Substitute the verified canonical fence as-is or strip to the
    "Could not render that diagram." note. No SymPy, no sampling — safe to
    run after a solve timeout.
    """
    content = _replace_unclosed_graph_fence(content, canonical_fence, densify=False)
    return _degrade_closed_diagram_fences(content, canonical_fence)


def _degrade_closed_diagram_fences(content: str, canonical_fence: dict[str, object] | None) -> str:
    """Strip closed unmatched geometry/graph fences. No SymPy densify."""
    content = map_closed_fences(
        content,
        "geometry",
        lambda body: _replace_fence(body, "geometry", canonical_fence, densify=False),
    )
    return map_closed_fences(
        content,
        "graph",
        lambda body: _replace_fence(body, "graph", canonical_fence, densify=False),
    )


def _replace_fence(
    raw: str,
    label: str,
    canonical_fence: dict[str, object] | None,
    canonical_fences: list[dict[str, object]] | None = None,
    *,
    densify: bool = True,
) -> str:
    """Replace a model geometry/graph fence with the canonical JSON, or strip it.

    Schema-valid invented numbers must not ship. There is no pass-through
    path for unmatched fences.
    """
    raw = raw.strip()
    corrected = _canonical_replacement(raw, canonical_fence, canonical_fences)
    if corrected is None:
        return _DIAGRAM_FAIL_NOTE
    if label != "graph":
        return f"```{label}\n{corrected}\n```"
    # Densify only the verified canonical curve — never an unverified
    # model expr (that would polish a wrong function into looking true).
    try:
        parsed = GraphBlockSpec.model_validate(json.loads(corrected))
    except (json.JSONDecodeError, ValidationError, TypeError):
        return f"```{label}\n{corrected}\n```"
    densified = densify_sparse_graph(parsed) if densify else parsed
    if densified is parsed:
        return f"```graph\n{corrected}\n```"
    return _graph_fence_body(densified)


def _canonical_answer_body(verified: VerifiedMathBlock | None) -> str | None:
    if verified is None:
        return None
    if verified.display_answer and verified.display_answer.strip():
        return verified.display_answer.strip()
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
    # Checked before the key heuristics below, and that ordering is
    # load-bearing: a scene carries `x_min` too, so the "looks like a graph"
    # fallback would claim it and render a projectile as an empty pair of axes.
    if spec_type in SIMULATION_SPEC_TYPES:
        return "simulation"
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


def _verified_includes_graph(verified: VerifiedMathBlock) -> bool:
    return any(_spec_fence_kind(spec) == "graph" for spec in _collect_canonical_specs(verified))


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
    """Read complete dollar or TeX-delimited formulas in one forward scan."""
    spans: list[str] = []
    index = 0
    while index < len(prose):
        if prose.startswith((r"\(", r"\["), index):
            closer = r"\)" if prose[index + 1] == "(" else r"\]"
            start = index + 2
        elif prose[index] == "\\":
            # Escaped dollars and literal backslashes are not math openers.
            index += 2
            continue
        elif prose[index] == "$":
            closer = "$$" if prose.startswith("$$", index) else "$"
            start = index + len(closer)
        else:
            index += 1
            continue
        end = prose.find(closer, start)
        if end < 0:
            break
        spans.append(prose[start:end])
        index = end + len(closer)
    return spans


def _span_states_short_int(span: str, core: str) -> bool:
    compact = _normalize_answer_token(span)
    return compact == core or compact.endswith("=" + core)


def _span_var_equals_int(span: str) -> str | None:
    """``x = 2`` / ``x=0`` → the integer core; skip ``2x = 4``."""
    compact = _normalize_answer_token(span)
    if len(compact) < 3 or not compact[0].isalpha() or compact[1] != "=":
        return None
    rest = compact[2:]
    if rest.startswith("-"):
        rest = rest[1:]
    if not rest.isdigit() or len(rest) > 2:
        return None
    return compact[2:]


def _compact_bare_var_equals_ints(compact: str) -> list[str]:
    """Integer cores from ``<letter>=N`` where the letter is not ``2x=4``."""
    found: list[str] = []
    i = 0
    n = len(compact)
    while i < n - 2:
        if (
            compact[i].isalpha()
            and compact[i + 1] == "="
            and (i == 0 or not compact[i - 1].isalnum())
        ):
            j = i + 2
            if j < n and compact[j] == "-":
                j += 1
            k = j
            while k < n and compact[k].isdigit():
                k += 1
            if k > j and (k - j) <= 2:
                found.append(compact[i + 2 : k])
            i = k
        else:
            i += 1
    return found


def _prose_states_conflicting_var_equals(content: str, answer_body: str) -> bool:
    """True when steps already state ``x = 2`` and the solver chip would be ``x = 0``."""
    solver = _answer_numeric_core(answer_body)
    digits = solver[1:] if solver.startswith("-") else solver
    if not digits.isdigit() or len(digits) > 2:
        return False
    stated: list[str] = []
    for span in _math_spans(content):
        hit = _span_var_equals_int(span)
        if hit is not None:
            stated.append(hit)
    stated.extend(_compact_bare_var_equals_ints(_normalize_answer_token(content)))
    return any(value != solver for value in stated)


def _normalize_math_answer_expression(text: str) -> str:
    """Compare harmless TeX spelling differences, preserving grouped powers."""
    # Remove spacing commands before whitespace/command slashes are stripped.
    # Word boundaries keep \quad from binding inside a different command name.
    spaced = re.sub(r"\\(?:qquad|quad)(?![A-Za-z])", "", text)
    for spacing in (r"\,", r"\;", r"\:", r"\!", "\\ "):
        spaced = spaced.replace(spacing, "")
    # Upright unit lettering is presentation only, but unit case is semantic:
    # mJ and MJ must never compare equal. Keep this fallback case-sensitive.
    spaced = re.sub(r"\\mathrm\{([A-Za-z°]{1,24})\}", r"\1", spaced)
    cleaned = (
        spaced.replace(r"\left", "")
        .replace(r"\right", "")
        .replace("$", "")
        .replace("\u2212", "-")
        .replace("\\", "")
    )
    compact = "".join(cleaned.split())
    # Only one literal atom: x^{12} and x^12 are different TeX expressions,
    # as are x^{1/6} and x^1/6. Never remove arbitrary grouping braces.
    return re.sub(r"\^\{([A-Za-z0-9])\}", r"^\1", compact)


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
    if r"\mathrm{" not in body and needle in _normalize_answer_token(content):
        return True
    # Formatting equivalence applies to complete math results only. A looser
    # substring check would find canonical x^{1} inside the different x^12.
    expression = _normalize_math_answer_expression(body)
    for span in _math_spans(content):
        stated = _normalize_math_answer_expression(span)
        if stated == expression or stated.endswith("=" + expression):
            return True
    return False


_MAX_SYMBOLIC_ANSWER_CHECKS = 2


def _answer_rhs(text: str) -> str:
    """Right-hand side of the last ``=`` (or the whole body for a bare result)."""
    body = text.strip().strip("$").strip()
    equals = body.rfind("=")
    return body[equals + 1 :].strip() if equals >= 0 else body


def _sympy_expr_or_none(text: str):  # type: ignore[no-untyped-def]
    """Parse a prose/latex answer candidate into a SymPy expression; None on failure."""
    candidate = _answer_rhs(text)
    if not candidate or len(candidate) > 120:
        return None
    try:
        return math_solve._parse_expression(candidate)
    except Exception:
        return None


def _prose_symbolically_states_answer(content: str, answer_body: str) -> bool:
    """SymPy-proven equivalence between the canonical answer and a prose math span.

    The string paths above miss harmless value spelling differences — prose
    ``$0.5$`` next to a canonical ``\\frac{1}{2}`` used to earn a duplicate
    answer chip. validate_math_fences runs inside the SymPy worker
    (``validate_math_fences_worker``), so this shares the existing post-stream
    budget; it adds no new latency class. This only ever *suppresses* a
    duplicate chip on proof of equivalence — every failure returns False,
    which appends the chip exactly as today.
    """
    canonical = _sympy_expr_or_none(answer_body)
    if canonical is None:
        return False
    # A bare prose expression (no "=") only counts when the canonical answer is
    # a bare number. Symbolically ``x^12`` == ``x^{12}``, but as *rendered*
    # prose the unbraced grouping displays differently — the chip must stay.
    canonical_is_bare_number = "=" not in answer_body and not any(
        ch.isalpha() for ch in _answer_rhs(answer_body)
    )
    checks = 0
    for span in _math_spans(content):
        if checks >= _MAX_SYMBOLIC_ANSWER_CHECKS:
            break
        if "=" not in span and not canonical_is_bare_number:
            continue
        candidate = _sympy_expr_or_none(span)
        if candidate is None:
            continue
        checks += 1
        if _sympy_equivalent(candidate, canonical):
            return True
    return False


def _sympy_equivalent(a, b) -> bool:  # type: ignore[no-untyped-def]
    """SymPy ``equals`` with the undecidable/exception cases folded to False."""
    try:
        return bool(a.equals(b))
    except Exception:
        logger.debug("symbolic answer comparison failed", exc_info=True)
        return False


# Emphasis and code ticks trailing the question mark: "**...?**", "...?*".
_TRAILING_MARKUP = "*_`~ \t"


def _line_asks(line: str) -> bool:
    return line.rstrip(_TRAILING_MARKUP).endswith("?")


def _reply_asks_instead_of_answering(content: str, answer_body: str | None) -> bool:
    """True when the reply requests information rather than giving a result.

    The fences below are solver-owned — the model is told not to emit them, so
    they are attached whenever they are missing. "Missing" was read as "the
    model forgot", because nothing here could tell that apart from a reply that
    deliberately has no answer in it. So when the model correctly answered a 2D
    collision with *"Which ball's final path is at 30°?"*, the pipeline pinned a
    verified ``0.79 m`` and a trajectory chart underneath the question.

    Both halves are needed, and the second is the one that keeps this safe. A
    question mark alone proves nothing: *"The range is about 35.31 m. Would you
    like the maximum height?"* answers first and asks second, and must keep its
    chart. It is the *absence* of an answer beside the question that makes a
    reply a request for more information.

    Position, on the other hand, proves nothing either way, which the incident
    itself showed: its question is the opening line and its closing line is a
    plain statement, so "the reply ends with a question" would have missed the
    very case this exists for. Any line that asks counts.

    A solver that produced no answer at all is the third case, and it is not
    this one. Angles alone fix a triangle's shape but not its size, so the
    solver returns a diagram, no number, and the reply asks for a side length —
    a question and no stated answer, yet the diagram is exactly right. What
    makes the incident wrong is a *verified answer* being pinned to a reply that
    does not make it, so with no such answer there is nothing to withhold.
    """
    if not answer_body:
        return False
    if not any(_line_asks(line) for line in content.splitlines()):
        return False
    return not _prose_already_states_answer(content, answer_body)


def _append_missing_canonical_fences(content: str, verified: VerifiedMathBlock | None) -> str:
    """Attach solver-owned fences the model was told not to emit."""
    if verified is None:
        return content
    answer_body = _canonical_answer_body(verified)
    # A reply that asks rather than answers has no answer to decorate, so it
    # gets no pill, no diagram and no chart — not one of the three.
    if _reply_asks_instead_of_answering(content, answer_body):
        return content
    extras: list[str] = []
    if (
        answer_body
        and not any(has_closed_fence(content, lang) for lang in _ANSWER_FENCE_LANGS)
        and not _prose_already_states_answer(content, answer_body)
        and not _prose_states_conflicting_var_equals(content, answer_body)
        and not _prose_symbolically_states_answer(content, answer_body)
    ):
        extras.append(_markdown_fence("answer", answer_body))

    specs = _collect_canonical_specs(verified)
    geo = next((spec for spec in specs if _spec_fence_kind(spec) == "geometry"), None)
    if geo is not None and not has_closed_fence(content, "geometry"):
        extras.append(_markdown_fence("geometry", json.dumps(geo, separators=(",", ":"))))
    graph = next((spec for spec in specs if _spec_fence_kind(spec) == "graph"), None)
    if graph is not None and not has_closed_fence(content, "graph"):
        extras.append(_markdown_fence("graph", json.dumps(graph, separators=(",", ":"))))
    scene = next((spec for spec in specs if _spec_fence_kind(spec) == "simulation"), None)
    if scene is not None and not has_closed_fence(content, "simulation"):
        extras.append(_markdown_fence("simulation", json.dumps(scene, separators=(",", ":"))))

    if not extras:
        return content
    stripped = content.rstrip()
    if stripped:
        return stripped + "\n\n" + "\n\n".join(extras) + "\n"
    return "\n\n".join(extras) + "\n"


def _replace_answer_fence(raw: str, answer_body: str | None) -> str:
    """Rewrite ```answer / ```result / ```final from SymPy, or demote to prose."""
    if not answer_body:
        body = raw.strip()
        # Keep a trailing newline so the next fence opener stays on its own line.
        return f"{body}\n" if body else ""
    return f"```answer\n{answer_body}\n```"


def _function_call_json_to_graph_fence(raw: str) -> str:
    """Drop ``!function_call:{...}`` blobs.

    Graph calls used to be sampled into a ```graph fence from the model's
    expr, which shipped unverified curves. Canonical graphs are appended
    after rewrite instead. Parse only so a truncated blob still strips.
    """
    try:
        json.loads(raw)
    except json.JSONDecodeError:
        return ""
    return ""


def convert_function_call_text(content: str) -> str:
    """Find ``!function_call:{...}`` blobs (balanced JSON, may span lines)
    and strip each one. Canonical graph fences are appended separately."""
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
    # of the structured tool_calls API — strip it so unverified graph JSON
    # never ships. Canonical diagrams are appended after rewrite.
    content = convert_function_call_text(content)
    for lang in _ANSWER_FENCE_LANGS:
        content = map_closed_fences(
            content,
            lang,
            lambda body: _replace_answer_fence(body, answer_body),
            max_count=_MAX_ANSWER_FENCES,
        )
    content = map_closed_fences(
        content,
        "geometry",
        lambda body: _replace_fence(
            body,
            "geometry",
            canonical_fence,
            canonical_fences,
        ),
        max_count=_MAX_GEOMETRY_FENCES,
        leftover=lambda _body: _DIAGRAM_FAIL_NOTE,
    )
    content = map_closed_fences(
        content,
        "graph",
        lambda body: _replace_fence(
            body,
            "graph",
            canonical_fence,
            canonical_fences,
        ),
        max_count=_MAX_GRAPH_FENCES,
        leftover=lambda _body: _DIAGRAM_FAIL_NOTE,
    )
    # A scene is server-owned and the prompt forbids it, but a model that
    # invents one would otherwise ship a hand-written physics animation. Same
    # treatment as geometry: replaced by the canonical scene, or struck out.
    content = map_closed_fences(
        content,
        "simulation",
        lambda body: _replace_fence(
            body,
            "simulation",
            canonical_fence,
            canonical_fences,
        ),
        max_count=_MAX_SIMULATION_FENCES,
        leftover=lambda _body: _DIAGRAM_FAIL_NOTE,
    )
    # A ```graph fence the model truncated mid-JSON (stopped copying the
    # verified points at EOS) is left unclosed. Swap it for the verified
    # canonical fence so the renderer gets a complete spec.
    content = _replace_unclosed_graph_fence(content, canonical_fence)
    # Vega ```chart is a different product from a verified function plot.
    # Drop the model's chart when we already own a ```graph fence.
    if verified is not None and _verified_includes_graph(verified):
        for lang in _CHART_ALIAS_LANGS:
            content = strip_closed_fences(content, lang)
        content = strip_closed_fences(content, "mermaid")
        content = strip_gfm_pipe_tables(content)
        content = strip_hand_sketch_filler(content)
    return _append_missing_canonical_fences(content, verified)


_FENCE_VALIDATE_MARKERS = (
    "```answer",
    "```result",
    "```final",
    "```graph",
    "```geometry",
    "```math",
)


def needs_math_fence_validate(content: str, verified: VerifiedMathBlock | None) -> bool:
    """Skip the SymPy pool when the reply has nothing for this rewriter."""
    if verified is not None:
        return True
    lower = content.lower()
    return any(marker in lower for marker in _FENCE_VALIDATE_MARKERS)


def validate_math_fences_worker(content: str, verified: VerifiedMathBlock | None = None) -> str:
    """Picklable entry for ``sympy_executor.run_sympy`` (positional args only)."""
    return validate_math_fences(content, verified=verified)


_UNVERIFIED_MATH_NOTE = "*Couldn't verify this with SymPy.*"

# Any digit, inline `$...$`, or a LaTeX macro. Deliberately blunt: the first
# attempt looked for an operator or an `=` and dropped the note from "The mass
# is 12 kg.", a verified-physics answer where it belongs. A false positive here
# only preserves the existing behavior; a false negative hides the note on a
# real math reply, so anything numeric counts.
_MATH_PRESENCE_RE = re.compile(r"[0-9]|\$[^$\n]+\$|\\[A-Za-z]+")


def _reply_contains_math(content: str) -> bool:
    """Is there anything in this reply the note could be talking about?"""
    lower = content.lower()
    if any(marker in lower for marker in _FENCE_VALIDATE_MARKERS):
        return True
    return _MATH_PRESENCE_RE.search(content) is not None


def append_unverified_math_note(content: str) -> str:
    """Honest label when camera/solver intent fired but SymPy produced nothing.

    Italic markdown in the reply body — not a banned assistant status chip.

    Skipped when the reply holds no math at all. The note is stamped whenever
    a math block was injected and SymPy returned nothing, so every extractor
    false positive reaches here: a chat about anatomy answered "show me" and
    ended with *Couldn't verify this with SymPy.* Guarding the stamp makes the
    whole class fail quietly instead of one misfire at a time.
    """
    if _UNVERIFIED_MATH_NOTE in content:
        return content
    if not _reply_contains_math(content):
        return content
    stripped = content.rstrip()
    if not stripped:
        return _UNVERIFIED_MATH_NOTE
    return f"{stripped}\n\n{_UNVERIFIED_MATH_NOTE}"
