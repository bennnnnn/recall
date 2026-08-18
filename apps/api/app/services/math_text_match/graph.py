"""Coordinate / plot / graph-expression cues."""

from __future__ import annotations

from app.services.math_text_match.scan import _BARE_COORD, _NUM


def _parse_xy_pair(token: str) -> tuple[float, float] | None:
    """Parse ``x,y`` or mobile-slip ``x.y`` (comma key next to period)."""
    compact = token.replace(" ", "")
    if compact.startswith("(") and compact.endswith(")"):
        compact = compact[1:-1]
    if "," in compact:
        parts = compact.split(",", 1)
    elif compact.count(".") == 1:
        # "2.3" keyboard slip for "2,3"
        parts = compact.split(".", 1)
    else:
        return None
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def bare_coord(text: str) -> tuple[float, float] | None:
    compact = text.replace(" ", "")
    m = _BARE_COORD.match(compact)
    if m:
        return float(m.group("x")), float(m.group("y"))
    # "(2.3)" slip
    if compact.startswith("(") and compact.endswith(")"):
        return _parse_xy_pair(compact)
    return None


def plot_point(text: str) -> tuple[float, float] | None:
    lower = text.lower()
    if "point" not in lower:
        return None
    if not any(v in lower for v in ("plot ", "mark ", "graph ", "show ", "mark point")):
        return None
    idx = lower.find("point")
    rest = text[idx + len("point") :].strip()
    if rest.startswith("("):
        close_p = rest.find(")")
        if close_p != -1:
            return _parse_xy_pair(rest[: close_p + 1])
    # "mark point 2, 3"
    return _parse_xy_pair(rest.split(")")[0])


def graph_expr(text: str) -> str | None:
    lower = text.lower()
    for prefix in ("graph ", "plot "):
        idx = lower.find(prefix)
        if idx == -1:
            continue
        expr = text[idx + len(prefix) :].strip()
        if expr.lower().startswith("y="):
            expr = expr[2:].lstrip()
        elif expr.lower().startswith("y ="):
            expr = expr[3:].lstrip()
        return expr or None
    return None


_GRAPH_PAIR_PREFIXES = ("graph ", "plot ", "compare ")
_GRAPH_PAIR_TRAILING_FILLER = (
    " on the same graph",
    " on the same plot",
    " on the same axes",
    " on one graph",
    " together",
)
_EXPR_CANDIDATE_CHARS = frozenset(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-*/().^= ."
)
# "plot sin(x) and explain it" must NOT be read as a second function named
# "explain it" — an explicit denylist (matching this module's existing
# preference for phrase tables over fuzzy heuristics) catches ordinary
# trailing prose that first_dim_pair-style character scanning can't.
_PROSE_WORDS = frozenset(
    (
        "explain",
        "it",
        "please",
        "why",
        "how",
        "what",
        "tell",
        "describe",
        "me",
        "this",
        "that",
        "show",
        "draw",
        "the",
        "a",
        "an",
        "is",
        "are",
        "these",
        "functions",
        "function",
        "curve",
        "curves",
        "then",
    )
)


def _strip_leading_y_equals(expr: str) -> str:
    lower = expr.lower()
    if lower.startswith("y="):
        return expr[2:].lstrip()
    if lower.startswith("y ="):
        return expr[3:].lstrip()
    return expr


def _looks_like_expr_candidate(s: str) -> bool:
    stripped = s.strip()
    if not stripped or len(stripped) > 120:
        return False
    if not all(c in _EXPR_CANDIDATE_CHARS for c in stripped):
        return False
    return not any(w in _PROSE_WORDS for w in stripped.lower().split())


def graph_expr_pair(text: str) -> tuple[str, str] | None:
    """ "graph EXPR1 and EXPR2 [on the same graph]" -> (EXPR1, EXPR2). Only
    matches when exactly one " and " splits the post-trigger text into two
    non-empty, expression-shaped candidates — checked BEFORE the single-
    expression graph_expr so a two-function ask doesn't get garbled into one
    unparseable expr, but a plain "plot sin(x) and explain it" still falls
    through to the single-expression path instead of treating "explain it"
    as a second function."""
    lower = text.lower()
    for prefix in _GRAPH_PAIR_PREFIXES:
        idx = lower.find(prefix)
        if idx == -1:
            continue
        rest = text[idx + len(prefix) :].strip()
        and_idx = rest.lower().find(" and ")
        if and_idx == -1:
            continue
        first = _strip_leading_y_equals(rest[:and_idx].strip())
        second = rest[and_idx + len(" and ") :].strip()
        second_lower = second.lower()
        for suffix in _GRAPH_PAIR_TRAILING_FILLER:
            if second_lower.endswith(suffix):
                second = second[: -len(suffix)].strip()
                break
        second = _strip_leading_y_equals(second)
        if _looks_like_expr_candidate(first) and _looks_like_expr_candidate(second):
            return first, second
    return None


def vertical_line_x(text: str) -> float | None:
    lower = text.lower().replace(" ", "")
    # x=<num> after a graph/plot/draw/vertical cue
    if "x=" not in lower:
        return None
    if not any(
        k in text.lower()
        for k in ("graph", "plot", "draw", "show", "sketch", "visuali", "vertical")
    ):
        return None
    idx = lower.find("x=")
    m = _NUM.match(lower, idx + 2)
    if m is None:
        return None
    # "x=2y" / "x=2*y" are functions (y = x/2), not a vertical line at x=2 —
    # _NUM grabs the leading "2" and ignores the trailing expression. Reject
    # when the digit run is followed by a variable or expression char so it
    # falls through to the function-graph extractor, which solves for y.
    # A trailing period/comma (sentence boundary) or end-of-string is fine.
    end = m.end()
    if end < len(lower) and (lower[end].isalnum() or lower[end] in "*/^("):
        return None
    return float(m.group(0))
