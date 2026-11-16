"""Geometry dimension reading: ``8 by 5 cm``, ``3x4x5``, ``radius 5``, ``legs 3 and 4``.

Also the shape and draw words the geometry extractors require. Linear scans (CodeQL-safe).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.services.number_text import DECIMAL, DECIMAL_LITERAL
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


# Between a measure's name and its number only these may stand: "radius of 3", "the
# height of the cylinder is 10", "the radius of its base is 3 cm", "side length 5",
# "radius r = 3". "height is twice its radius of 3" names no height.
_LINK_WORDS = frozenset(
    """
    of is are was = : equals equal to its the a an base length measures measure measuring
    r h d l w b s cylinder cone sphere hemisphere pyramid prism cuboid box cube solid circle
    triangle rectangle square parallelogram trapezoid trapezium rhombus kite sector figure shape
    """.split()
)
_NUMBER = re.compile(rf"(?<![\d.,]){DECIMAL}")
# A number that is only the start of a measure: 50√2, 5 root 3, 3π, 1/2, 1½, 2,5, 3 x 10²,
# 2^3, 4e5.
_GLUED_AFTER = re.compile(
    r"[\u00bc-\u00be\u2150-\u215e\u00b2\u00b3\u00b9\u2070-\u2079]|,\d|[eE][+-]?\d"
)
_SPACED_AFTER = re.compile(
    r"\u221a|sqrt|root|\u03c0|\\pi\b|pi\b|/\s*\d|\^|\*\*|[x\u00d7*\u00b7]\s*\d", re.IGNORECASE
)
_ROOT_SIGNS = ("\u221a", "sqrt", "root")


def _after_root(before: str) -> bool:
    """``√2``, ``sqrt(2)``, ``root 3``: the number is under a root sign."""
    stripped = before.rstrip()
    if stripped.endswith(("(", "{")):
        stripped = stripped[:-1].rstrip()
    return stripped.lower().endswith(_ROOT_SIGNS)


def _slanted(before: str) -> bool:
    """A slant height or slant-height is not the solid's height."""
    return before.rstrip(" \t\n-").endswith("slant")


def _whole_number(text: str, number: re.Match[str]) -> float | None:
    """``number`` read whole: None when a root, π, a fraction, a decimal comma or a power
    makes the measure more than that number."""
    rest = text[number.end() :]
    if (
        _GLUED_AFTER.match(rest)
        or _SPACED_AFTER.match(rest.lstrip())
        or _after_root(text[: number.start()])
    ):
        return None
    return float(number.group(0))


def _read_after(text: str, lower: str, end: int) -> float | bool | None:
    """The measure after a name ending at ``end``: its value, None when no number follows
    at all, False when the next number is not this name's."""
    number = _NUMBER.search(text, end)
    if number is None:
        return None
    between = re.findall(r"[a-z]+|[^\sa-z]", lower[end : number.start()])
    if not all(word in _LINK_WORDS for word in between):
        return False
    found = _whole_number(text, number)
    return False if found is None else found


def _names(lower: str, label: str) -> list[re.Match[str]]:
    return [
        name
        for name in re.finditer(rf"(?<![a-z]){re.escape(label)}(?![a-z])", lower)
        if not _slanted(lower[: name.start()])
    ]


def measure_after(text: str, label: str) -> float | None:
    """The measure stated right after ``label``, read whole, or None.

    The number must follow its name with only linking words between (never the next
    number anywhere: "radius ½ m and height 4 m" has no radius 4), and the whole
    number must be read: a root, π, a fraction, a decimal comma or a power after it
    means the measure is not that number. A slant height is not the height, so a
    reader that took "slant height 50√2" as a height of 50 now declines.
    """
    lower = text.lower()
    for name in _names(lower, label):
        found = _read_after(text, lower, name.end())
        return None if found is None or found is False else float(found)
    return None


def measures_after(text: str, label: str) -> list[float]:
    """Every measure stated right after ``label`` ("radius 3 cm ... radius 5 cm"), each read
    as ``measure_after`` reads one."""
    lower = text.lower()
    found = [_read_after(text, lower, name.end()) for name in _names(lower, label)]
    return [float(value) for value in found if value is not None and value is not False]


# A measure named after it: "6 m wide", "8 m up the wall", "1.2 m in diameter": the number,
# its unit (one word, or none) and the name.
_BEFORE_NAME = re.compile(rf"(?<![\d.,])({DECIMAL})\s*(?:([a-z]+)\.?)?\s+$")


def measures_before(text: str, label: str, is_unit: Callable[[str], bool]) -> list[float]:
    """Every measure stated right before ``label``, with a unit (``is_unit``) or none
    between: "a box 8 cm long" is 8 before "long", "8 apples long" is none."""
    lower = text.lower()
    found: list[float] = []
    for name in _names(lower, label):
        before = _BEFORE_NAME.search(lower, max(0, name.start() - 24), name.start())
        if before is None or (before.group(2) and not is_unit(before.group(2))):
            continue
        number = _NUMBER.match(text, before.start(1))
        value = _whole_number(text, number) if number is not None else None
        if value is not None:
            found.append(value)
    return found


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
