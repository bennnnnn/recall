"""Geometry dimension reading: ``8 by 5 cm``, ``3x4x5``, ``radius 5``, ``legs 3 and 4``.

Also the shape and draw words the geometry extractors require. Linear scans (CodeQL-safe).
"""

from __future__ import annotations

import re

from app.services.number_text import DECIMAL_LITERAL
from app.services.text_match import word_index

_DIM_SEPS = ("\u00d7", "by", "x", "*")
_DIM_UNITS = ("units", "unit", "cm", "mm", "ft", "in", "m")

_GEOMETRY_DIM_WORDS = (
    "rectangle",
    "triangle",
    "square",
    "circle",
    "trapezoid",
    "trapezium",
    "parallelogram",
    "diagonal",
    "sector",
    "prism",
    "cuboid",
)


def _parse_unsigned_number(s: str, start: int = 0) -> tuple[float, int] | None:
    """Parse ``digits`` or ``digits.digits`` / ``digits,digits`` at ``start``.

    A comma with no space before the fraction (``3,5``) is a decimal, not a
    thousands/list split.
    """
    n = len(s)
    i = start
    if i >= n or not s[i].isdigit():
        return None
    while i < n and s[i].isdigit():
        i += 1
    if i < n and s[i] in ".,":
        j = i + 1
        if j < n and s[j].isdigit():
            while j < n and s[j].isdigit():
                j += 1
            i = j
        # else: "5." at end of a sentence — keep the integer, ignore the period.
    try:
        return float(s[start:i].replace(",", ".")), i
    except ValueError:
        return None


def geometry_dim_context(lower: str) -> bool:
    """Shape / diagonal words that geometry extractors actually require.

    ``first_dim_pair`` alone matches ``8*2`` inside ``8-8*2``. The gate must
    not treat that as verified geometry.
    """
    padded = f" {lower} "
    if " rect " in padded:
        return True
    return any(word_index(lower, cue) != -1 for cue in _GEOMETRY_DIM_WORDS)


_DRAW_VERB = re.compile(r"\b(?:draw|show|sketch|visuali[sz]e)\s", re.IGNORECASE)
# Capitalised words a plain shape may follow in Title Case: "Draw An Equilateral Triangle".
_SHAPE_WORDS = frozenset(
    {
        "a", "an", "the", "this", "that", "my", "your", "one", "two", "three", "four",
        "right", "equilateral", "isosceles", "scalene", "acute", "obtuse", "regular", "unit",
    }
)  # fmt: skip


def has_draw_shape(cleaned: str, shape: str) -> bool:
    """A draw, show or sketch verb with ``shape`` (lower case) as a plain shape.

    A capitalised word before the shape makes it a name, not a figure to draw: "a
    flowchart of a Punnett square", "Times Square", "Pascal's triangle".
    """
    lower = cleaned.lower()
    if shape not in lower or _DRAW_VERB.search(cleaned) is None:
        return False
    for match in re.finditer(re.escape(shape), lower):
        words = cleaned[: match.start()].split()
        previous = words[-1] if words else ""
        name = previous.removesuffix("'s").removesuffix("\u2019s")
        if not name[:1].isupper() or name.lower() in _SHAPE_WORDS:
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
    m = DECIMAL_LITERAL.search(text, idx + len(label))
    return float(m.group(0)) if m else None


def two_numbers_after(text: str, label: str) -> tuple[float, float] | None:
    """``legs 3 and 4`` / ``legs 3, 4`` → (3, 4). Linear ``find`` + digit scan."""
    lower = text.lower()
    idx = lower.find(label)
    if idx == -1:
        return None
    found: list[float] = []
    pos = idx + len(label)
    while True:
        m = DECIMAL_LITERAL.search(text, pos)
        if m is None:
            break
        try:
            found.append(float(m.group(0)))
        except ValueError:
            pos = m.end()
            continue
        if len(found) >= 2:
            return found[0], found[1]
        pos = m.end()
    return None
