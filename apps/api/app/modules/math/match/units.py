"""Small unit vocabulary for text extraction; solvers retain dimensional checks."""

from __future__ import annotations

import re

from app.services.unit_text import LENGTH_UNITS, unit_after_quantity


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
    from app.modules.math.match.scan import _NUM

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
    from app.modules.math.match.scan import _NUM

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
