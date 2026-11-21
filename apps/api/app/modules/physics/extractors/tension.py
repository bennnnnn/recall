"""Tension and vector extractors: Atwood, a vertical rope, resultants, any vector's components."""

from __future__ import annotations

import re

from app.modules.physics.extractors.angles import INCLINE_ANGLE_RE
from app.modules.physics.extractors.assignments import strip_param_assignments
from app.modules.physics.extractors.cues import (
    has_cue,
)
from app.modules.physics.extractors.stated_values import (
    find_value_with_specific_unit,
    ordered_values,
)
from app.modules.physics.extractors.unit_patterns import DECIMAL, DEGREE_WORD
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import to_si
from app.services.text_match import has_equation

_TENSION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\A(?=.*\btension\b)(?=.*\d\s*(?:kg|lbs?|oz)\b)"
        r"(?=.*(?:lift|rais|hoist|hang|suspend|hold|support|lower|descend|elevator))",
        re.IGNORECASE | re.DOTALL,
    ),
    # An Atwood pair often never says "tension" at all.
    re.compile(r"\batwood\b", re.IGNORECASE),
    re.compile(r"\bpulley\b.{0,80}?\d\s*(?:kg|lbs?|oz)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:kg|lbs?|oz)\b.{0,80}?\bpulley\b", re.IGNORECASE),
)

_TENSION_UP_RE = re.compile(
    r"\blift(?:s|ing|ed)?\b|\brais(?:e|es|ing|ed)\b|\bhoist\w*\b|\bpull(?:s|ed|ing)?\s+up\b"
    r"|\bupwards?\b|\bris(?:e|es|ing)\b|\bascend\w*\b|\baccelerat\w*\s+up\w*\b",
    re.IGNORECASE,
)

_TENSION_DOWN_RE = re.compile(
    r"\blower(?:s|ing|ed)?\b|\bdescend\w*\b|\bdownwards?\b|\bfall(?:s|ing)\b|\bdropp?(?:s|ing|ed)\b",
    re.IGNORECASE,
)

_TENSION_STATIC_RE = re.compile(
    r"\bhang(?:s|ing)?\b|\bsuspend\w*\b|\bhold(?:s|ing)?\b|\bsupport(?:s|ing)?\b"
    r"|\bstationary\b|\bat rest\b|\bequilibrium\b",
    re.IGNORECASE,
)

_UNSUPPORTED_TENSION_CONTEXT = (
    "incline",
    "ramp",
    "slope",
    "angle",
    "degree",
    "°",
    "friction",
    "coefficient",
    "horizontal",
    "floor",
    "table",
    "across",
    "two ropes",
    "both ropes",
    "each rope",
    "two cables",
    "both cables",
    "each cable",
    "two strings",
    "each string",
)


def _extract_tension_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not has_cue(lower, (), _TENSION_CUE_RES):
        return None
    if any(word in lower for word in _UNSUPPORTED_TENSION_CONTEXT):
        return None
    if has_equation(strip_param_assignments(cleaned)):
        return None

    masses = ordered_values(cleaned, r"kg|lbs?|oz")
    if not masses:
        return None

    # --- Atwood: two masses sharing one pulley --------------------------------
    is_pair = "atwood" in lower or "pulley" in lower
    if is_pair and len(masses) >= 2:
        # The heavier mass descends, so ordering them here makes the sign of
        # the acceleration a property of the physics rather than of the
        # sentence. Its magnitude is what the question asks for either way.
        heavy, light = sorted(
            (masses[0], masses[1]),
            key=lambda pair: to_si(pair[0], pair[1] or "kg"),
            reverse=True,
        )
        return PhysicsIntent(
            kind="force",
            physics_op="atwood",
            physics_params={"m1": heavy[0], "m2": light[0]},
            physics_units={"m1": heavy[1] or "kg", "m2": light[1] or "kg"},
            operation="solve",
        )
    if is_pair:
        # A pulley with one mass named is an incomplete Atwood, not a hanging
        # mass: the rope runs over the pulley to something we were not told
        # about. Refusing beats assuming the other side is fixed.
        return None

    # --- a single rope, which must be vertical -------------------------------
    goes_up = _TENSION_UP_RE.search(cleaned) is not None
    goes_down = _TENSION_DOWN_RE.search(cleaned) is not None
    is_static = _TENSION_STATIC_RE.search(cleaned) is not None
    if not (goes_up or goes_down or is_static):
        return None

    params: dict[str, float] = {"m": masses[0][0]}
    units: dict[str, str] = {"m": masses[0][1] or "kg"}
    accel = find_value_with_specific_unit(
        cleaned,
        r"m/s\^?2|m/s2",
        ("acceleration", "accelerates", "accelerating", "accelerated"),
    )
    if accel is not None:
        value, unit = accel
        # Down is the only direction that has to be stated; "supporting a mass
        # accelerating at 2 m/s^2" reads as upward, which is what P2's example
        # meant by 59.05 N.
        params["a"] = -value if goes_down else value
        units["a"] = unit or "m/s^2"

    return PhysicsIntent(
        kind="force",
        physics_op="tension",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


_VECTOR_FORCE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bresultant\b.{0,80}?\d\s*N\b", re.IGNORECASE),
    re.compile(r"\d\s*N\b.{0,80}?\bresultant\b", re.IGNORECASE),
    # Any vector resolved: its size in any of ``_VECTOR_SIZE_RE``'s units, and an angle.
    re.compile(
        rf"\A(?=.*\b(?:resolv\w*|components?)\b)(?=.*\d\s*{DEGREE_WORD})",
        re.IGNORECASE | re.DOTALL,
    ),
)

_PERPENDICULAR_RE = re.compile(
    rf"\bperpendicular\b|\bright angles?\b|\bat 90\s*{DEGREE_WORD}"
    r"|\b(?:north|south)\b.{0,60}?\b(?:east|west)\b|\b(?:east|west)\b.{0,60}?\b(?:north|south)\b"
    r"|\bhorizontal\b.{0,60}?\bvertical\b|\bvertical\b.{0,60}?\bhorizontal\b",
    re.IGNORECASE,
)

_ANGLE_BETWEEN_RE = re.compile(
    rf"({DECIMAL})\s*{DEGREE_WORD}(?:[^.]{{0,40}}?"
    r"(?:to each other|between them|apart|to one another))",
    re.IGNORECASE,
)

_RESOLVE_RE = re.compile(r"\bresolv\w*\b|\bcomponents?\b", re.IGNORECASE)

# A vector's size, by the unit it is written in, and the parameter it is: a force, a field, an
# acceleration, a velocity, a momentum, a displacement. Longer spellings first, so "m/s" is
# never read as metres and "N/C" never as newtons. The unit is kept as written: a component
# of 1900 km is in km.
_VECTOR_SIZE_RE = re.compile(
    rf"({DECIMAL})\s*(N\s*/\s*C|V\s*/\s*m|m\s*/\s*s\s*(?:\^\s*2|²)|(?:k?m|cm)\s*/\s*[sh]"
    r"|kg\s*m\s*/\s*s|N\s*s|km|cm|mm|m|N)(?![A-Za-z0-9/^²])"
)
_VECTOR_PARAMS = (
    (re.compile(r"N\s*/\s*C|V\s*/\s*m"), "E"),
    (re.compile(r"m\s*/\s*s\s*(?:\^\s*2|²)"), "a"),
    (re.compile(r"(?:k?m|cm)\s*/\s*[sh]"), "v"),
    (re.compile(r"kg\s*m\s*/\s*s|N\s*s"), "p"),
    (re.compile(r"km|cm|mm|m"), "d"),
    (re.compile(r"N"), "F"),
)
# Components along a slope or a line, not across and up: weight on an incline is its own law.
# An angle from the normal is a ray's or a surface's, and a field, a wire or a charge has its
# own law that uses a component inside it (review, 2026-11-20). A rope's pull is a vector
# like any: a mass and a length beside it make two values, never one (``_stated_values``).
_NOT_AXES_RE = re.compile(
    r"\b(?:incline[ds]?|slope|ramp|along|parallel|normal|magnetic|wire|current|charge[ds]?"
    r"|proton|electron|ray|light|refract\w*|thermometer|temperature)\b",
    re.IGNORECASE,
)
# The angle's reference, written right after it: "40° from the vertical", "30 degrees to the
# y-axis". Read only there: "the vertical component" elsewhere names a component asked for.
_AFTER_ANGLE_VERTICAL_RE = re.compile(
    r"\s*(?:from|to|with|of)\s+the\s+(?:vertical|y[- ]?axis|upward\s+vertical)\b", re.IGNORECASE
)
_BELOW_RE = re.compile(r"\bbelow\s+the\s+(?:horizontal|x[- ]?axis)\b", re.IGNORECASE)
# A bearing: "30° north of east" is measured from east; "40° east of north" from north.
_BEARING_RE = re.compile(
    r"\b(north|south|east|west)\s+of\s+(north|south|east|west)\b", re.IGNORECASE
)
# A three-figure bearing, clockwise from north: "on a bearing of 040°", "bearing 120°".
_NUMBER_BEARING_RE = re.compile(
    rf"\bbearing\s+(?:of\s+)?({DECIMAL})\s*{DEGREE_WORD}?", re.IGNORECASE
)
# Any value with a unit. A resolving question states one, the vector's size, besides its angle.
_STATED_VALUE_RE = re.compile(r"(?<![\w.])\d[\d.,]*\s*([A-Za-zµμΩ°][\w/^²³*·]*)")
_ANGLE_OR_COUNT_RE = re.compile(r"°|deg\w*|rad\w*|components?$|parts?$|times$", re.IGNORECASE)
# A question that asks for more than the components (a range, a time, a height) is a bigger
# problem, answered by its own law or the model: "the components of velocity and the range".
_MORE_ASKED_RE = re.compile(
    r"\b(?:range|how\s+(?:far|long|high)|maximum|max\.?|time\s+of\s+flight|height|"
    r"resultant|net|magnitude\s+and\s+direction)\b",
    re.IGNORECASE,
)


def _stated_values(cleaned: str) -> int:
    """How many measured values the question states, angles and counts left out."""
    return sum(
        1
        for match in _STATED_VALUE_RE.finditer(cleaned)
        if not _ANGLE_OR_COUNT_RE.match(match.group(1))
    )


def _resolve_intent(cleaned: str) -> PhysicsIntent | None:
    """One vector of any kind split into horizontal and vertical components, its angle from
    the horizontal, the vertical or a compass bearing, each component signed by its side.

    A resolving question states one measured value, the vector, and asks for nothing more;
    anything else (a mass beside a rope, a field beside a wire, the range of a throw) is a
    problem a component is only a step of (review, 2026-11-20)."""
    if _NOT_AXES_RE.search(cleaned) or _MORE_ASKED_RE.search(cleaned):
        return None
    size = _VECTOR_SIZE_RE.search(cleaned)
    if size is None or _stated_values(cleaned) != 1:
        return None
    numbered = _NUMBER_BEARING_RE.search(cleaned)
    angle = INCLINE_ANGLE_RE.search(cleaned) if numbered is None else numbered
    if angle is None:
        return None
    unit = " ".join(re.sub(r"\s*/\s*", "/", size.group(2)).split()).replace("²", "^2")
    name = next(param for pattern, param in _VECTOR_PARAMS if pattern.fullmatch(unit))
    params = {name: float(size.group(1)), "angle": float(angle.group(1))}
    bearing = _BEARING_RE.search(cleaned)
    if numbered is not None:
        # Clockwise from north: the sine is east, the cosine north, each signed by itself.
        params.update(from_vertical=1.0, x_sign=1.0, y_sign=1.0)
    elif bearing is not None:
        toward, base = bearing.group(1).lower(), bearing.group(2).lower()
        sides = {toward, base}
        if sides in ({"north", "south"}, {"east", "west"}):
            return None
        params["from_vertical"] = 1.0 if base in ("north", "south") else 0.0
        params["x_sign"] = -1.0 if "west" in sides else 1.0
        params["y_sign"] = -1.0 if "south" in sides else 1.0
    else:
        vertical = _AFTER_ANGLE_VERTICAL_RE.match(cleaned, angle.end()) is not None
        params["from_vertical"] = 1.0 if vertical else 0.0
        params["x_sign"] = 1.0
        params["y_sign"] = -1.0 if _BELOW_RE.search(cleaned) else 1.0
    return PhysicsIntent(
        kind="force",
        physics_op="resolve_vector",
        physics_params=params,
        physics_units={name: unit, "angle": "deg"},
        operation="solve",
    )


def _extract_vector_force_intent(cleaned: str) -> PhysicsIntent | None:
    if not has_cue(cleaned.lower(), (), _VECTOR_FORCE_CUE_RES):
        return None
    if has_equation(strip_param_assignments(cleaned)):
        return None

    forces = ordered_values(cleaned, r"N")

    # --- resultant of two forces -------------------------------------------
    if "resultant" in cleaned.lower() and len(forces) >= 2:
        between = _ANGLE_BETWEEN_RE.search(cleaned)
        if between is not None:
            phi = float(between.group(1))
        elif _PERPENDICULAR_RE.search(cleaned):
            phi = 90.0
        else:
            # Two forces and no stated geometry is not a resultant question
            # anyone can answer — the angle between them is the whole problem.
            return None
        return PhysicsIntent(
            kind="force",
            physics_op="resultant_force",
            physics_params={"F1": forces[0][0], "F2": forces[1][0], "angle": phi},
            physics_units={"F1": "N", "F2": "N", "angle": "deg"},
            operation="solve",
        )

    # --- one vector split into components ------------------------------------
    if _RESOLVE_RE.search(cleaned):
        return _resolve_intent(cleaned)

    return None
