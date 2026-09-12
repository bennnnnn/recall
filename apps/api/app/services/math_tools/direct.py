"""Direct verified-math replies that skip the LLM when language adds nothing."""

from __future__ import annotations

import json
import math

from app.services.math_tools.block.common import VerifiedMathBlock

# Linear phrase scan — do not put user text through nested-optional regex
# (CodeQL py/polynomial-redos). Substrings are enough: "explain every step"
# should keep the LLM; "1+1=x" should not.
_EXPLAIN_PHRASES: tuple[str, ...] = (
    "explain",
    "teach",
    "show work",
    "show your work",
    "show me your work",
    "show me work",
    "show the steps",
    "show me the steps",
    "show me how",
    "show working",
    "step by step",
    "step-by-step",
    "walk me",
    "why is",
    "why does",
    "how do",
    "how does",
    "how to",
    "how can",
    "how would",
)

# Imperative / polite glue around a closed compute. Two leftover English
# words beyond this ("tell" + "joke") keep the LLM.
_MATH_REQUEST_GLUE = frozenset(
    {
        "solve",
        "isolate",
        "factor",
        "expand",
        "simplify",
        "calculate",
        "compute",
        "evaluate",
        "determine",
        "find",
        "please",
        "thanks",
        "thank",
        "now",
        "quickly",
        "briefly",
        "here",
        "what",
        "whats",
        "the",
        "value",
        "of",
        "for",
        "and",
        "then",
        "is",
        "equals",
        "equal",
        "plus",
        "minus",
        "times",
        "can",
        "you",
        "could",
        "this",
        "that",
    }
)

_MAX_DIRECT_ANSWER_CHARS = 400


def _plot_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    if isinstance(value, str) and len(value) > 64:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _literal_plot_point(text: str) -> tuple[float, float] | None:
    value = text.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    parts = value.split(",")
    if len(parts) != 2:
        return None
    x, y = (_plot_number(part.strip()) for part in parts)
    return (x, y) if x is not None and y is not None else None


def _can_direct_point_or_vertical(verified: VerifiedMathBlock, user_text: str) -> bool:
    """Match a complete literal plot request, never a coordinate substring."""
    if len(user_text) > 1000:
        return False
    fences = _solver_fences(verified)
    if len(fences) != 1:
        return False
    graph = fences[0]
    if graph.get("expr2") or graph.get("points2") or graph.get("variable", "x") != "x":
        return False
    request = " ".join(user_text.split()).replace("\u2212", "-")
    if request.lower().startswith("please "):
        request = request[7:].lstrip()
    for prefix in ("plot ", "graph ", "mark ", "show ", "draw ", "sketch "):
        if request.lower().startswith(prefix):
            request = request[len(prefix) :].strip().rstrip(".?")
            break
    else:
        return False
    if request.lower().startswith("the "):
        request = request[4:]
    if graph.get("type") == "vertical":
        if verified.canonical_answer:
            return False
        for prefix in ("vertical line ", "line "):
            if request.lower().startswith(prefix):
                request = request[len(prefix) :]
                break
        lhs, separator, rhs = request.partition("=")
        x = _plot_number(graph.get("x"))
        expr_lhs, expr_separator, expr_rhs = str(graph.get("expr") or "").partition("=")
        low, high = _plot_number(graph.get("y_min")), _plot_number(graph.get("y_max"))
        return bool(
            separator
            and lhs.strip().lower() == "x"
            and x is not None
            and _plot_number(rhs.strip()) == x
            and expr_separator
            and expr_lhs.strip().lower() == "x"
            and _plot_number(expr_rhs.strip()) == x
            and low is not None
            and high is not None
            and low < high
        )
    if graph.get("type") != "function" or not request.lower().startswith("point "):
        return False
    points = graph.get("points")
    if not isinstance(points, list) or len(points) != 1:
        return False
    point = points[0]
    if not isinstance(point, list) or len(point) != 2:
        return False
    x, y = (_plot_number(value) for value in point)
    if x is None or y is None:
        return False
    expected = (x, y)
    # All three canonical representations must describe the requested point.
    # Extra prose, a second coordinate, expressions, or unpaired brackets do
    # not parse as one numeric comma pair and retain the model path.
    return (
        _literal_plot_point(request[6:]) == expected
        and _literal_plot_point(str(graph.get("expr") or "")) == expected
        and _literal_plot_point(verified.canonical_answer or "") == expected
    )


def wants_math_explanation(text: str) -> bool:
    """True when the user asked for language (steps / teaching), not just the value."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in _EXPLAIN_PHRASES):
        return True
    padded = f" {lowered} "
    return " prove " in padded or " proof " in padded


def _looks_math_token(tok: str) -> bool:
    if not tok:
        return True
    return any(ch.isdigit() or ch in "=^*/+-%" for ch in tok)


def leftover_non_math_request(text: str) -> bool:
    """True when the message asks for something besides the verified value.

    ``Solve x+1=2 and tell me a joke`` must not become an instant ``x = 1``.
    Linear token walk — no regex on user text.
    """
    english = 0
    for raw in text.replace("'", "").split():
        tok = raw.lower().strip(".,?!:;")
        if _looks_math_token(tok) or len(tok) < 3 or tok in _MATH_REQUEST_GLUE:
            continue
        english += 1
        if english >= 2:
            return True
    return False


def _solver_fences(verified: VerifiedMathBlock) -> list[dict[str, object]]:
    fences: list[dict[str, object]] = []
    if verified.canonical_fence is not None:
        fences.append(verified.canonical_fence)
    for fence in verified.canonical_fences:
        if fence is not None and fence not in fences:
            fences.append(fence)
    return fences


def _plain_prime_factorization_request(text: str) -> bool:
    """Match the complete one-integer ask; extra clauses still need language."""
    if len(text) > 1000:
        return False
    request = " ".join(text.lower().split()).rstrip(".?")
    for prefix in ("please ", "can you ", "could you "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    for prefix in ("find ", "calculate ", "compute ", "determine ", "what is ", "what's "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    if request.startswith("the "):
        request = request[4:]
    for prefix in ("prime factorization of ", "prime factors of ", "factorize "):
        if request.startswith(prefix):
            number = request[len(prefix) :]
            if number.endswith(" please"):
                number = number[:-7]
            return bool(number and number.isascii() and number.isdecimal())
    return False


def _can_direct_graph(verified: VerifiedMathBlock, user_text: str) -> bool:
    """Match the whole plot request, not an expression extracted from one clause."""
    from app.services.math_text_match import graph_domain, prepare
    from app.services.math_text_match.graph import _GRAPH_PAIR_TRAILING_FILLER

    if len(user_text) > 1000 or verified.canonical_answer:
        return False
    fences = _solver_fences(verified)
    if len(fences) != 1 or fences[0].get("type") not in {"function", "inequality"}:
        return False
    graph = fences[0]
    points, expr = graph.get("points"), graph.get("expr")
    expr2, points2 = graph.get("expr2"), graph.get("points2")
    paired = bool(expr2 or points2)
    if not isinstance(expr, str) or not expr.strip() or graph.get("variable", "x") != "x":
        return False
    if graph.get("type") == "function" and (not isinstance(points, list) or len(points) < 2):
        return False
    if paired and (
        graph.get("type") != "function"
        or not isinstance(expr2, str)
        or not expr2.strip()
        or not isinstance(points2, list)
        or len(points2) < 2
        or graph.get("variable2") != "x"
    ):
        return False
    request = prepare(user_text)
    if not request:
        return False
    if request.lower().startswith("please "):
        request = request[7:].lstrip()
    for prefix in ("graph ", "plot ", "draw ", "sketch ", "visualize ", "visualise "):
        if request.lower().startswith(prefix):
            # Keep !: it may be a factorial that extraction did not preserve.
            request = request[len(prefix) :].strip().rstrip(".?")
            break
    else:
        return False
    domain = graph_domain(request)
    if domain is not None:
        lo, hi, request = domain
        # A range ignored by extraction or narrowed by sampling needs language.
        if graph.get("x_min") != lo or graph.get("x_max") != hi:
            return False
    if paired:
        for suffix in _GRAPH_PAIR_TRAILING_FILLER:
            if request.lower().endswith(suffix):
                request = request[: -len(suffix)].rstrip()
                break
        split_at = request.lower().find(" and ")
        if split_at < 0:
            return False
        clauses = (request[:split_at].strip(), request[split_at + 5 :].strip())
        for clause, sampled_expr in zip(clauses, (expr, expr2), strict=True):
            if "=" in clause:
                lhs, _, clause = clause.partition("=")
                if lhs.strip().lower() != "y":
                    return False
            # Reuse the exact sampled expressions, preserving any extra
            # request, third curve, factorial, or ignored domain as a mismatch.
            if clause.replace(" ", "").replace("^", "**") != str(sampled_expr).replace(
                " ", ""
            ).replace("^", "**"):
                return False
        return True
    if (
        graph.get("type") == "function"
        and "=" in expr
        and request.replace(" ", "").replace("^", "**") == expr.replace(" ", "").replace("^", "**")
    ):
        # The verified circle/ellipse sampler preserves the whole relation
        # and closes its parametric loop; it is not a y=f(x) expression.
        return isinstance(points, list) and len(points) >= 3 and points[0] == points[-1]
    if graph.get("type") == "function" and "=" in request:
        lhs, _, request = request.partition("=")
        if lhs.strip().lower() != "y":
            return False
    # The verified sampler preserves its input expr. Requiring the entire
    # remaining request to match it keeps "and solve/explain/tell me..." and
    # additional formulas on the model path, without another SymPy parse.
    return request.replace(" ", "").replace("^", "**") == expr.replace(" ", "").replace("^", "**")


def _can_direct_number_line(verified: VerifiedMathBlock, user_text: str) -> bool:
    """A whole inequality solve can display its answer and solution set directly."""
    from app.services.math_service.parse import _rewrite_bare_abs_bars
    from app.services.math_text_match import prepare

    answer = (verified.canonical_answer or "").strip()
    fences = _solver_fences(verified)
    if (
        len(user_text) > 1000
        or not answer
        or len(answer) > _MAX_DIRECT_ANSWER_CHARS
        or len(fences) != 1
        or fences[0].get("type") != "number_line"
    ):
        return False
    expr = fences[0].get("expr")
    request = prepare(user_text)
    if not isinstance(expr, str) or not expr.strip() or not request:
        return False
    if request.lower().startswith("please "):
        request = request[7:].lstrip()
    if not request.lower().startswith("solve "):
        return False
    request = request[6:].strip()
    if request.lower().startswith("the inequality "):
        request = request[15:].lstrip()
    # Keep factorials and all remaining prose/domain clauses intact. Only
    # spelling-equivalent operators and whitespace can differ from the exact
    # inequality the solver used; no new symbolic parsing or prose whitelist.
    request = request.rstrip(".?")

    def compact(value: str) -> str:
        return (
            _rewrite_bare_abs_bars(value)
            .replace(" ", "")
            .replace("^", "**")
            .replace("≤", "<=")
            .replace("≥", ">=")
            .replace("\u2212", "-")
        )

    return compact(request) == compact(expr.rstrip(".?"))


def can_direct_verified_math_reply(
    verified: VerifiedMathBlock,
    user_text: str,
    *,
    has_image_attachment: bool = False,
) -> bool:
    """Skip the LLM for a short closed answer or an explicit verified function plot.

    Geometry, camera homework, explanations, and mixed requests keep the
    current inject+stream path.
    """
    if has_image_attachment:
        return False
    if not verified.allow_direct:
        return False
    if wants_math_explanation(user_text):
        return False
    from app.services.math_tools.direct_geometry import (
        can_direct_rectangle,
        can_direct_square_or_triangle,
        can_direct_triangle_angles,
    )

    geometry_fences = _solver_fences(verified)
    if can_direct_triangle_angles(user_text, geometry_fences):
        return True
    if can_direct_rectangle(verified, user_text, geometry_fences) or can_direct_square_or_triangle(
        verified, user_text, geometry_fences
    ):
        return True
    if _can_direct_point_or_vertical(verified, user_text):
        return True
    if _can_direct_graph(verified, user_text):
        return True
    if _can_direct_number_line(verified, user_text):
        return True
    # Prime factorization has two operation words, which the generic prose
    # counter rejects. Require a whole-request match instead of whitelisting
    # them globally; even "factorize 60 and 2+2" must retain the model path.
    from app.services.math_text_match.coordinate_vector import (
        has_coordinate_vector_request,
        is_closed_coordinate_vector_request,
    )
    from app.services.math_tools.direct_statistics import statistics_direct_request
    from app.services.math_tools.direct_units import unit_direct_request

    statistics_request = statistics_direct_request(user_text)
    unit_request = unit_direct_request(user_text)
    if statistics_request is False or unit_request is False:
        return False
    if statistics_request or unit_request:
        fences = _solver_fences(verified)
        if (
            len(fences) != 1
            or fences[0].get("type") != "answer"
            or fences[0].get("content") != verified.canonical_answer
        ):
            return False
    lower = user_text.lower()
    coordinate_vector_request = has_coordinate_vector_request(user_text)
    if coordinate_vector_request and not is_closed_coordinate_vector_request(user_text):
        return False
    factorization_request = "prime factor" in lower or "factorize" in lower
    if factorization_request and not _plain_prime_factorization_request(user_text):
        return False
    if not (
        factorization_request or coordinate_vector_request or statistics_request or unit_request
    ) and leftover_non_math_request(user_text):
        return False
    answer = (verified.canonical_answer or "").strip()
    if not answer or len(answer) > _MAX_DIRECT_ANSWER_CHARS:
        return False
    fences = _solver_fences(verified)
    if not fences:
        return True
    return all(fence.get("type") == "answer" for fence in fences)


def format_direct_math_reply(verified: VerifiedMathBlock) -> str:
    """Display a verified value or the existing canonical function plot."""
    fences = _solver_fences(verified)
    answer = (verified.canonical_answer or "").strip()
    if len(fences) == 1 and fences[0].get("relative_lengths") is True:
        return f"```geometry\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
    if len(fences) == 1 and fences[0].get("type") in {"function", "inequality", "vertical"}:
        # The mobile stream scanner needs the newline after the closing fence
        # to render the graph immediately, before the done event arrives.
        graph_reply = f"```graph\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
        if answer:
            return f"```answer\n{answer}\n```\n\n{graph_reply}"
        return graph_reply
    if len(fences) == 1 and fences[0].get("type") in {
        "rectangle",
        "square",
        "triangle",
        "right_triangle",
        "triangle_sides",
    }:
        return (
            f"```answer\n{answer}\n```\n\n"
            f"```geometry\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
        )
    if len(fences) == 1 and fences[0].get("type") == "number_line":
        return (
            f"```answer\n{answer}\n```\n\n"
            f"```graph\n{json.dumps(fences[0], separators=(',', ':'))}\n```\n"
        )
    # The answer fence already typesets the result. Emitting a second math
    # paragraph repeats the same answer on the phone. The final newline also
    # lets the streaming client close and render this fence immediately.
    return f"```answer\n{answer}\n```\n"


def maybe_direct_math_reply(
    verified: VerifiedMathBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
) -> str | None:
    if verified is None:
        return None
    if not can_direct_verified_math_reply(
        verified, user_text, has_image_attachment=has_image_attachment
    ):
        return None
    return format_direct_math_reply(verified)
