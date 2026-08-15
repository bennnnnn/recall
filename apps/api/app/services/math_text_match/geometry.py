"""Solid / triangle-side homework cues."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.math_text_match.scan import (
    _NUM,
    first_dim_pair,
    first_dim_triple,
    number_after,
)
from app.services.math_text_match.types import SolidShape

_SOLID_ALGEBRA_PHRASES = (
    "cube root",
    "cubic",
    "cubed",
    "cube of",
    "perfect cube",
)


def classify_solid_shape(lower: str) -> SolidShape | None:
    """3D homework shapes. Algebraic 'cube' (cube root, cubic) is not a solid."""
    if "rectangular prism" in lower or "rect prism" in lower or "cuboid" in lower:
        return "rectangular_prism"
    if "cylinder" in lower:
        return "cylinder"
    if "cone" in lower:
        return "cone"
    if "sphere" in lower:
        return "sphere"
    if "pyramid" in lower:
        return "pyramid"
    if "cube" in lower and not any(p in lower for p in _SOLID_ALGEBRA_PHRASES):
        return "cube"
    return None


def solid_homework_cue(lower: str) -> bool:
    padded = f" {lower} "
    return (
        " volume" in padded
        or padded.startswith("volume ")
        or "surface area" in lower
        or "surface-area" in lower
        or "capacity" in lower
    )


@dataclass(frozen=True)
class SolidParse:
    shape: SolidShape
    width: float | None = None
    height: float | None = None
    depth: float | None = None
    side: float | None = None
    radius: float | None = None
    unit: str = "cm"
    wants_volume: bool = False
    wants_surface_area: bool = False


def _solid_complete(parsed: SolidParse) -> bool:
    if parsed.shape == "cube":
        return parsed.side is not None
    if parsed.shape == "rectangular_prism":
        return parsed.width is not None and parsed.height is not None and parsed.depth is not None
    if parsed.shape in {"cylinder", "cone"}:
        return parsed.radius is not None and parsed.height is not None
    if parsed.shape == "sphere":
        return parsed.radius is not None
    if parsed.shape == "pyramid":
        if parsed.height is None:
            return False
        if parsed.side is not None:
            return True
        return parsed.width is not None and parsed.depth is not None
    return False


def parse_solid(cleaned: str) -> SolidParse | None:
    """Volume/surface-area homework with printed measures — never invent dims."""
    lower = cleaned.lower()
    shape = classify_solid_shape(lower)
    if shape is None:
        return None
    if geometry_deferred_for_algebra(lower):
        return None
    padded = f" {lower} "
    wants_volume = solid_homework_cue(lower) and "surface" not in lower
    wants_sa = "surface area" in lower or "surface-area" in lower
    if wants_sa and "volume" in padded:
        wants_volume = True
    if not wants_volume and not wants_sa:
        wants_volume = True

    unit = "cm"
    triple = first_dim_triple(cleaned)
    pair = first_dim_pair(cleaned)
    side = number_after(cleaned, "side") or number_after(cleaned, "edge")
    radius = number_after(cleaned, "radius")
    diameter = number_after(cleaned, "diameter")
    height = number_after(cleaned, "height")
    length = number_after(cleaned, "length")
    width = number_after(cleaned, "width")
    depth = number_after(cleaned, "depth")
    base = number_after(cleaned, "base")
    if diameter is not None and radius is None:
        radius = diameter / 2.0
    if triple is not None:
        unit = triple[3]
    elif pair is not None:
        unit = pair[2]

    width_v = width
    height_v = height
    depth_v = depth
    side_v = side if side is not None else base
    if shape == "cube":
        if side_v is None:
            side_v = _first_positive_number(cleaned)
    elif shape == "rectangular_prism":
        if triple is not None:
            width_v, depth_v, height_v = triple[0], triple[1], triple[2]
        else:
            labeled = [v for v in (length, width, depth, height) if v is not None]
            if len(labeled) >= 3:
                width_v, depth_v, height_v = labeled[0], labeled[1], labeled[2]
            else:
                width_v = width_v or length or (pair[0] if pair else None)
                depth_v = depth_v or (pair[1] if pair else None)
    elif shape in {"cylinder", "cone"}:
        if height_v is None and pair is not None:
            if radius is None:
                radius, height_v = pair[0], pair[1]
            else:
                height_v = pair[1] if pair[0] == radius else pair[0]
    elif shape == "sphere":
        if radius is None:
            radius = _first_positive_number(cleaned)
    elif shape == "pyramid":
        if height_v is None and triple is not None:
            width_v, depth_v, height_v = triple[0], triple[1], triple[2]
        elif side_v is None and pair is not None and height_v is not None:
            side_v = pair[0]
        elif side_v is None and width_v is None and triple is None:
            if pair is not None:
                width_v, depth_v = pair[0], pair[1]

    parsed = SolidParse(
        shape=shape,
        width=width_v,
        height=height_v,
        depth=depth_v,
        side=side_v,
        radius=radius,
        unit=unit,
        wants_volume=wants_volume,
        wants_surface_area=wants_sa,
    )
    if not _solid_complete(parsed):
        return None
    return parsed


def _first_positive_number(text: str) -> float | None:
    m = _NUM.search(text)
    if m is None:
        return None
    value = float(m.group(0))
    return value if value > 0 else None


def geometry_deferred_for_algebra(lower: str) -> bool:
    """Geometry extractors run *before* equation/graph extractors.

    A phrase like "solve x^2+y^2=25 for the circle of radius 5" used to match
    the circle extractor (radius present) and steal the algebra path. Defer
    geometry when the ask is clearly algebraic — unless the user also asked
    to draw/show/sketch the shape.
    """
    if any(v in lower for v in ("draw ", "show ", "sketch ", "visualize ", "visualise ")):
        return False
    padded = f" {lower} "
    return any(
        cue in padded
        for cue in (
            " equation ",
            " equations ",
            " solve ",
            " algebra ",
            " complete the square ",
            " unit circle ",
            " expand ",
            " factor ",
            " differentiate ",
            " derivative ",
            " integrate ",
            " integral ",
        )
    )


_TRIANGLE_SIDES_PREFIXES = ("sides ", "side lengths ", "sides of ", "side lengths of ")


def triangle_sides_signal(text: str) -> tuple[float, float, float] | None:
    """ "triangle with sides 3, 4, 5" -> (3, 4, 5). Requires the word
    "triangle" AND a "sides" cue immediately before 3 numbers, so a bare
    "triangle" (handled by the existing base+height extractor) never matches."""
    lower = text.lower()
    if "triangle" not in lower:
        return None
    for prefix in _TRIANGLE_SIDES_PREFIXES:
        idx = lower.find(prefix)
        if idx == -1:
            continue
        nums = [m.group(0) for m in _NUM.finditer(text, idx + len(prefix))]
        if len(nums) >= 3:
            try:
                return float(nums[0]), float(nums[1]), float(nums[2])
            except ValueError:
                return None
    return None
