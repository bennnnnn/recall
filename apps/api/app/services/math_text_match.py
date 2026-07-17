"""Linear (non-regex / digit-only-regex) matchers for math intent heuristics.

Kept separate so CodeQL py/polynomial-redos cannot taint user chat text into
nested optional/``\\s`` regex pumps in ``math_tools.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.text_normalize import collapse_ws

_MAX = 1000
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_BARE_COORD = re.compile(r"^\((?P<x>-?\d+(?:\.\d+)?),(?P<y>-?\d+(?:\.\d+)?)\)$")
_CALC_OP = re.compile(
    r"\b(simplify|differentiate|derivative|integrate|integral|factor|expand)\b",
    re.IGNORECASE,
)
_DIM_SEPS = ("\u00d7", "by", "x", "*")
_DIM_UNITS = ("units", "unit", "cm", "mm", "ft", "in", "m")


def _parse_unsigned_number(s: str, start: int = 0) -> tuple[float, int] | None:
    """Parse ``digits`` or ``digits.digits`` at ``start``; return (value, end)."""
    n = len(s)
    i = start
    if i >= n or not s[i].isdigit():
        return None
    while i < n and s[i].isdigit():
        i += 1
    if i < n and s[i] == ".":
        j = i + 1
        if j >= n or not s[j].isdigit():
            return None
        while j < n and s[j].isdigit():
            j += 1
        i = j
    try:
        return float(s[start:i]), i
    except ValueError:
        return None


def prepare(text: str) -> str | None:
    cleaned = collapse_ws(text)
    if len(cleaned) > _MAX:
        return None
    return cleaned


def has_draw_shape(lower: str, shape: str) -> bool:
    if shape not in lower:
        return False
    return any(v in lower for v in ("draw ", "show ", "sketch ", "visualize ", "visualise "))


def has_math_keyword(lower: str) -> bool:
    compact = lower.replace(" ", "")
    if "y=" in compact:
        return True
    for phrase in (
        "solve",
        "simplify",
        "factor",
        "expand",
        "differentiate",
        "derivative",
        "integrate",
        "integral",
        "equation",
        "algebra",
        "quadratic",
        "polynomial",
        "find the angle",
        "diagonal",
        "rectangle",
        "triangle",
        "circle",
        "geometry",
        "radius",
        "diameter",
        "circumference",
        "graph",
        "plot",
        "function",
        "sqrt",
        "square root",
        "pythagor",
    ):
        if phrase in lower:
            return True
    return False


def has_equation(text: str) -> bool:
    eq = text.find("=")
    if eq <= 0 or eq >= len(text) - 1:
        return False
    if text[eq + 1 : eq + 2] == "=":
        return False
    lhs, rhs = text[:eq].strip(), text[eq + 1 :].strip()
    return bool(lhs and rhs and any(c.isalnum() for c in lhs) and any(c.isalnum() for c in rhs))


def first_dim_pair(text: str) -> tuple[float, float, str] | None:
    # Collapse "8 x 5 cm" → "8x5cm" so separators are adjacent (no space pumps).
    compact = (
        text.replace(" \u00d7 ", "\u00d7")
        .replace(" x ", "x")
        .replace(" * ", "*")
        .replace(" by ", "by")
        .replace(" ", "")
    )
    lower = compact.lower()
    n = len(compact)
    i = 0
    while i < n:
        a_hit = _parse_unsigned_number(compact, i)
        if a_hit is None:
            i += 1
            continue
        a, j = a_hit
        sep_len = 0
        for sep in _DIM_SEPS:
            if lower.startswith(sep, j):
                sep_len = len(sep)
                break
        if not sep_len:
            i += 1
            continue
        b_hit = _parse_unsigned_number(compact, j + sep_len)
        if b_hit is None:
            i += 1
            continue
        b, k = b_hit
        unit = "cm"
        for cand in _DIM_UNITS:
            if lower.startswith(cand, k):
                unit = "units" if cand.startswith("unit") else cand
                break
        return a, b, unit
    return None


def number_after(text: str, label: str) -> float | None:
    lower = text.lower()
    idx = lower.find(label)
    if idx == -1:
        return None
    m = _NUM.search(text, idx + len(label))
    return float(m.group(0)) if m else None


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
    return float(m.group(0)) if m else None


def calc_op(text: str) -> str | None:
    m = _CALC_OP.search(text)
    return m.group(1).lower() if m else None


def _match_limit_point(s: str) -> tuple[str, int] | None:
    """Match infinity / oo / number at start of ``s``; return (token, end)."""
    low = s.lower()
    for tok in ("-infinity", "infinity", "-inf", "inf", "-oo", "oo"):
        if low.startswith(tok):
            return s[: len(tok)], len(tok)
    start = 1 if s.startswith("-") else 0
    hit = _parse_unsigned_number(s, start)
    if hit is None or (start == 1 and hit[1] == 1):
        return None
    return s[: hit[1]], hit[1]


def _parse_signed_int_token(s: str) -> tuple[str, int] | None:
    start = 1 if s.startswith("-") else 0
    if start >= len(s) or not s[start].isdigit():
        return None
    i = start
    while i < len(s) and s[i].isdigit():
        i += 1
    return s[:i], i


@dataclass(frozen=True)
class LimitHit:
    expr: str
    var: str
    point: str


def _parse_latex_limit(text: str) -> LimitHit | None:
    """Parse ``\\lim_{x \\to 0} expr`` without optional-space regex pumps."""
    idx = text.find("\\lim")
    if idx == -1:
        return None
    rest = text[idx + 4 :]
    while rest.startswith("_") or rest.startswith(" "):
        rest = rest[1:]
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    if not rest or not rest[0].isalpha():
        return None
    var = rest[0]
    rest = rest[1:].lstrip(" ")
    arrow = None
    for candidate in ("\\to", "->", "→"):
        if rest.startswith(candidate):
            arrow = candidate
            break
    if arrow is None:
        return None
    rest = rest[len(arrow) :].lstrip(" ")
    point_hit = _match_limit_point(rest)
    if point_hit is not None:
        point, plen = point_hit
    elif rest.lower().startswith("-\\infty"):
        point, plen = "-\\infty", 7
    elif rest.lower().startswith("\\infty"):
        point, plen = "\\infty", 6
    else:
        return None
    rest = rest[plen:].lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    expr = rest.strip()
    if not expr:
        return None
    return LimitHit(expr=expr, var=var, point=point)


def parse_limit(text: str) -> LimitHit | None:
    lower = text.lower()
    # Compact: lim x->0 expr
    if lower.startswith("lim ") or " lim " in f" {lower} ":
        idx = lower.find("lim ")
        rest = text[idx + 4 :].strip()
        # var
        if not rest:
            return None
        var = rest[0]
        if not var.isalpha():
            return None
        rest_l = rest[1:].lstrip()
        for arrow in ("->", "→"):
            if rest_l.startswith(arrow):
                rest_l = rest_l[len(arrow) :].lstrip()
                break
        else:
            return None
        point_hit = _match_limit_point(rest_l)
        if not point_hit:
            return None
        point, pend = point_hit
        expr = rest_l[pend:].strip()
        if expr.lower().startswith("of "):
            expr = expr[3:].strip()
        if expr:
            return LimitHit(expr=expr, var=var, point=point)
    # Prose: ... as x approaches 0
    as_idx = lower.find(" as ")
    if as_idx != -1 and ("limit" in lower or "lim" in lower):
        before = text[:as_idx].strip()
        for lead in (
            "find ",
            "evaluate ",
            "compute ",
            "what is ",
            "determine ",
            "the ",
            "limit of ",
        ):
            low = before.lower()
            if low.startswith(lead):
                before = before[len(lead) :].strip()
        after = text[as_idx + 4 :].strip()
        if not after or not after[0].isalpha():
            return None
        var = after[0]
        rest = after[1:].lstrip().lower()
        for cue in ("approaches ", "goes to ", "tends to ", "->", "→", "to "):
            if rest.startswith(cue):
                rest = rest[len(cue) :].lstrip()
                break
        else:
            return None
        # prose uses "infinity" / "inf" / number (allow longer "infinity" spelling)
        point_hit = _match_limit_point(rest)
        if point_hit is None:
            for tok in ("-infinity", "infinity"):
                if rest.startswith(tok):
                    point_hit = (tok, len(tok))
                    break
        if not point_hit or not before:
            return None
        return LimitHit(expr=before, var=var, point=point_hit[0])
    return _parse_latex_limit(text)


@dataclass(frozen=True)
class SeriesHit:
    expr: str
    var: str
    start: str
    end: str


def _parse_latex_series(text: str) -> SeriesHit | None:
    """Parse ``\\sum_{n=1}^{\\infty} expr`` without optional-space regex pumps."""
    idx = text.find("\\sum")
    if idx == -1:
        return None
    rest = text[idx + 4 :]
    while rest.startswith("_") or rest.startswith(" "):
        rest = rest[1:]
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    if not rest or not rest[0].isalpha():
        return None
    var = rest[0]
    rest = rest[1:].lstrip(" ")
    if not rest.startswith("="):
        return None
    rest = rest[1:].lstrip(" ")
    start_hit = _parse_signed_int_token(rest)
    if start_hit is None:
        return None
    start, send = start_hit
    rest = rest[send:].lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    if not rest.startswith("^"):
        return None
    rest = rest[1:].lstrip(" ")
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    end_tok: str | None = None
    low = rest.lower()
    for tok in ("\\infty", "infinity"):
        if low.startswith(tok):
            end_tok = rest[: len(tok)]
            rest = rest[len(tok) :]
            break
    if end_tok is None:
        end_hit = _parse_signed_int_token(rest)
        if end_hit is None:
            return None
        end_tok, eend = end_hit
        rest = rest[eend:]
    rest = rest.lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    expr = rest.strip()
    if not expr:
        return None
    return SeriesHit(expr=expr, var=var, start=start, end=end_tok)


def parse_series(text: str) -> SeriesHit | None:
    lower = text.lower()
    if not any(k in lower for k in ("sum ", "series", "converge", "diverge")):
        # also bare "sum of"
        if "sum" not in lower:
            return None
    # sum|series [of] EXPR from VAR=START to END
    for head in ("sum of ", "series of ", "sum ", "series "):
        idx = lower.find(head)
        if idx == -1:
            continue
        rest = text[idx + len(head) :]
        from_idx = rest.lower().find(" from ")
        if from_idx == -1:
            continue
        expr = rest[:from_idx].strip()
        tail = rest[from_idx + 6 :].strip()
        parts = tail.replace(" ", "")
        # var=START to END — linear scan on compacted digits
        if not parts or not parts[0].isalpha():
            continue
        var = parts[0]
        if len(parts) < 2 or parts[1] != "=":
            continue
        after_eq = parts[2:]
        start_hit = _parse_signed_int_token(after_eq)
        if start_hit is None:
            continue
        start, send = start_hit
        after_start = after_eq[send:]
        if not after_start.lower().startswith("to"):
            continue
        after_to = after_start[2:]
        end_tok: str | None = None
        low_end = after_to.lower()
        for tok in ("infinity", "inf", "oo"):
            if low_end.startswith(tok):
                end_tok = after_to[: len(tok)]
                break
        if end_tok is None:
            end_hit = _parse_signed_int_token(after_to)
            if end_hit is None:
                continue
            end_tok = end_hit[0]
        if expr:
            return SeriesHit(expr=expr, var=var, start=start, end=end_tok)
    return _parse_latex_series(text)


def integral_bounds(expr: str) -> tuple[str, str, str] | None:
    """Return (expr_without_bounds, lo, hi) for trailing ``from LO to HI``."""
    lower = expr.lower()
    idx = lower.rfind(" from ")
    if idx == -1:
        return None
    head = expr[:idx].strip()
    tail = expr[idx + 6 :].strip()
    to_idx = tail.lower().find(" to ")
    if to_idx == -1:
        return None
    lo = tail[:to_idx].strip()
    hi = tail[to_idx + 4 :].strip()
    if head and lo and hi and " " not in hi:
        return head, lo, hi
    return None


def needs_symbolic(text: str, *, has_image_attachment: bool = False) -> bool:
    cleaned = prepare(text)
    if cleaned is None:
        return False
    if not cleaned and not has_image_attachment:
        return False
    from app.services.math_image_extract import is_math_camera_prompt

    if has_image_attachment and is_math_camera_prompt(cleaned):
        return True
    lower = cleaned.lower()
    if (
        has_draw_shape(lower, "rectangle")
        or has_draw_shape(lower, "right triangle")
        or has_draw_shape(lower, "square")
        or has_draw_shape(lower, "circle")
    ):
        return True
    if has_image_attachment and has_math_keyword(lower):
        return True
    if has_equation(cleaned) and has_math_keyword(lower):
        return True
    if first_dim_pair(cleaned) is not None:
        return True
    if "circle" in lower and (
        number_after(cleaned, "radius") is not None or number_after(cleaned, "diameter") is not None
    ):
        return True
    if bare_coord(cleaned) is not None or plot_point(cleaned) is not None:
        return True
    if graph_expr(cleaned) is not None:
        return True
    if vertical_line_x(cleaned) is not None:
        return True
    if calc_op(cleaned) is not None:
        return True
    if parse_limit(cleaned) is not None:
        return True
    if parse_series(cleaned) is not None:
        return True
    if "newton" in lower or "numerically" in lower or "root of" in lower:
        return True
    if "solve" in lower and has_equation(cleaned):
        return True
    return has_math_keyword(lower) and has_equation(cleaned)
