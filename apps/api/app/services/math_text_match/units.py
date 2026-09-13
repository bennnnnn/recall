"""Small unit vocabulary for text extraction; solvers retain dimensional checks."""

from __future__ import annotations

import re

LENGTH_UNITS = {
    alias: symbol
    for symbol, aliases in {
        "m": ("m", "meter", "meters", "metre", "metres"),
        "cm": ("cm", "centimeter", "centimeters", "centimetre", "centimetres"),
        "mm": ("mm", "millimeter", "millimeters", "millimetre", "millimetres"),
        "km": ("km", "kilometer", "kilometers", "kilometre", "kilometres"),
        "ft": ("ft", "foot", "feet"),
        "in": ("in", "inch", "inches"),
        "yd": ("yd", "yard", "yards"),
        "mi": ("mi", "mile", "miles"),
    }.items()
    for alias in aliases
}
TIME_UNITS = {
    alias: symbol
    for symbol, aliases in {
        "s": ("s", "sec", "secs", "second", "seconds"),
        "ms": ("ms", "millisecond", "milliseconds"),
        "min": ("min", "mins", "minute", "minutes"),
        "h": ("h", "hr", "hrs", "hour", "hours"),
        "day": ("day", "days"),
    }.items()
    for alias in aliases
}

_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
QUANTITY_NUMBER = re.compile(_NUMBER_PATTERN)


def unit_after_quantity(text: str, number_end: int) -> tuple[str, int] | None:
    """Read a unit once after an already scanned numeric token.

    A number-plus-unit regex search can retry its failing suffix from every
    digit. This anchored character walk never retries inside the number.
    """
    index = number_end
    while index < len(text) and text[index].isspace():
        index += 1
    start = index
    while index < len(text) and ("a" <= text[index] <= "z" or "A" <= text[index] <= "Z"):
        index += 1
    if index == start:
        return None
    # Keep the same whole-unit boundary: m/s, m^2, and m2 are not scalar m.
    if index < len(text) and (text[index] in "/^" or "0" <= text[index] <= "9"):
        return None
    return text[start:index], index


def normalize_leading_decimals(cleaned: str) -> str:
    """Make .5 and -.5 explicit before existing dimension-number scanners."""
    return re.sub(r"(?<![\w.])([+-]?)\.(?=\d)", r"\g<1>0.", cleaned)


_DIMENSION_GLUE = {
    "by",
    "x",
    "and",
    "with",
    "height",
    "width",
    "length",
    "depth",
    "side",
    "edge",
    "radius",
    "diameter",
    "base",
    "top",
    "bottom",
    "angle",
    "degree",
    "degrees",
    "diagonal",
    "area",
    "perimeter",
    "circumference",
    "please",
    "units",
    "unit",
}


def solid_length_unit(cleaned: str) -> str | None:
    """One consistent printed length unit, or generic units when none is given.

    Mixed units need per-dimension conversion; do not relabel those raw numbers
    as if they used the same scale.
    """
    from app.services.math_text_match.scan import _NUM

    found: set[str] = set()
    for number in _NUM.finditer(cleaned):
        after = cleaned[number.end() :].lstrip()
        word = re.match(r"[A-Za-z]+", after)
        if word is None:
            continue
        name = word.group(0).lower()
        if name in _DIMENSION_GLUE:
            continue
        suffix = after[word.end() :]
        if (
            name not in LENGTH_UNITS
            or suffix.lstrip().startswith(("/", "^", "²", "³"))
            or (suffix and suffix[0].isdigit())
        ):
            return None
        if name == "in":
            # "in the plane" / "in meters" is prose, not an inch measure.
            # Terminal "4 in" and repeated "3 in by 4 in" stay supported.
            following = re.match(r"[A-Za-z]+", suffix.lstrip())
            if following is not None and following.group(0).lower() not in (
                _DIMENSION_GLUE - {"unit", "units"}
            ):
                return None
        found.add(LENGTH_UNITS[name])
    if len(found) > 1:
        return None
    return next(iter(found), "units")


def strip_geometry_length_units(cleaned: str) -> str:
    """Let existing dimension scanners read both ``3 by 4 cm`` and ``3 cm by 4 cm``.

    The caller separately validates the single common unit. Strip only recognized
    scalar length tokens, never arbitrary words or compound units.
    """
    from app.services.math_text_match.scan import _NUM

    chunks: list[str] = []
    start = 0
    for number in _NUM.finditer(cleaned):
        unit = unit_after_quantity(cleaned, number.end())
        if unit is None or unit[0].lower() not in {*LENGTH_UNITS, "unit", "units"}:
            continue
        chunks.append(cleaned[start : number.end()])
        start = unit[1]
    chunks.append(cleaned[start:])
    return "".join(chunks)
