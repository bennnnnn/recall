"""Number / dimension scans (CodeQL-safe, mostly linear)."""

from __future__ import annotations

import re

from app.services.text_normalize import collapse_ws

_MAX = 1000
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_BARE_COORD = re.compile(r"^\((?P<x>-?\d+(?:\.\d+)?),(?P<y>-?\d+(?:\.\d+)?)\)$")
_CALC_OP = re.compile(
    r"\b(simplify|differentiate|derivative|integrate|integral|factor|expand|taylor|partial|dsolve)\b",
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


# A standalone single-letter variable (not part of a longer word) is a strong
# algebraic signal. "2x+3=7" → 'x' qualifies; "the meeting = 3pm" has no such
# letter (every letter sits inside a multi-letter word), so prose with an '='
# is not pulled into SymPy.
_STANDALONE_VAR_RE = re.compile(r"(?<![a-zA-Z])[a-zA-Z](?![a-zA-Z])")


def has_algebraic_equation(text: str) -> bool:
    """An equation that contains a standalone single-letter variable.

    Used to trigger SymPy for bare ``2x+3=7`` (no "solve"/"find" keyword)
    without dragging in prose that happens to contain an ``=``.
    """
    if not has_equation(text):
        return False
    return _STANDALONE_VAR_RE.search(text) is not None


def inequality_signal(cleaned: str) -> bool:
    """A clear algebraic inequality: a symbolic comparator (``<``, ``>``, ``≤``,
    ``≥``, ``<=``, ``>=``) with both a variable letter and a number nearby —
    ``"x > 4"``, ``"2x < 10"``, ``"1 < x < 5"``.

    Rejects prose (``"less than 5 minutes"`` — word, no symbol) and trivial
    comparisons (``"5 < 10"`` — no variable letter). The window is small (12
    chars each side) so a stray ``>`` in unrelated prose without a nearby digit
    + letter doesn't trip.
    """
    for m in re.finditer(r"<=|>=|≤|≥|<|>", cleaned):
        start = max(0, m.start() - 12)
        end = min(len(cleaned), m.end() + 12)
        window = cleaned[start:end]
        if any(c.isalpha() for c in window) and any(c.isdigit() for c in window):
            return True
    return False


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


def first_dim_triple(text: str) -> tuple[float, float, float, str] | None:
    """Parse ``3 by 4 by 5 cm`` / ``3x4x5`` — a 2-value pair is not enough."""
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
        sep1 = 0
        for sep in _DIM_SEPS:
            if lower.startswith(sep, j):
                sep1 = len(sep)
                break
        if not sep1:
            i += 1
            continue
        b_hit = _parse_unsigned_number(compact, j + sep1)
        if b_hit is None:
            i += 1
            continue
        b, k = b_hit
        sep2 = 0
        for sep in _DIM_SEPS:
            if lower.startswith(sep, k):
                sep2 = len(sep)
                break
        if not sep2:
            i += 1
            continue
        c_hit = _parse_unsigned_number(compact, k + sep2)
        if c_hit is None:
            i += 1
            continue
        c, m = c_hit
        unit = "cm"
        for cand in _DIM_UNITS:
            if lower.startswith(cand, m):
                unit = "units" if cand.startswith("unit") else cand
                break
        return a, b, c, unit
    return None


def number_after(text: str, label: str) -> float | None:
    lower = text.lower()
    idx = lower.find(label)
    if idx == -1:
        return None
    m = _NUM.search(text, idx + len(label))
    return float(m.group(0)) if m else None
