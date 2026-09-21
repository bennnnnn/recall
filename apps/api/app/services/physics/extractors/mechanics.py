"""Force, energy, momentum, collision, and friction extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.services.physics.extractors.common import (
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _detect_gravity,
    _find_value_with_specific_unit,
    _has_cue,
    _ordered_values,
    _strip_param_assignments,
)
from app.services.text_match import has_equation

_MOMENTUM_CUES = (
    "momentum",
    "impulse",
    "center of mass",
    "centre of mass",
    "collision",
    "collide",
    "collides",
    "recoil",
    "stick together",
    "sticks together",
)

_LANDING_TARGET = r"ground|floor|water|sea|surface|deck|earth|soil|sand|roof"

_COLLISION_SUBJECT_RE = re.compile(
    r"\bcollision\b|\bcollides?\b|\bcolliding\b|\brecoils?\b"
    rf"|\bhits?\b(?!\s+the\s+(?:{_LANDING_TARGET})\b)"
    rf"|\bstrikes?\b(?!\s+the\s+(?:{_LANDING_TARGET})\b)"
    r"|sticks? together|stuck together",
    re.IGNORECASE,
)

_TWO_DIMENSIONAL_RE = re.compile(
    r"\b2-?d\b|\btwo[- ]dimensional\b|\bdeflect(?:s|ed|ion)?\b"
    r"|\bat an angle\b|\bglancing\b|\boblique\b"
    r"|\d\s*(?:degrees?|deg|°)",
    re.IGNORECASE,
)

_ELASTIC_RE = re.compile(r"\belastic")

_INELASTIC_RE = re.compile(
    r"\binelastic|sticks? together|stuck together|"
    r"\bcoupled?\b|\bembed(?:s|ded)?\b|\block(?:s|ed)? together\b"
)

_MASS_UNITS = r"kg|mg|g|lb|lbs|oz"

_MOMENTUM_TIME_UNITS = r"milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"


def _extract_momentum_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _MOMENTUM_CUES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    masses = _ordered_values(cleaned, _MASS_UNITS)
    velocities = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)

    # --- Centre of mass: x_cm = sum(m_i x_i) / sum(m_i) ---------------
    if "center of mass" in lower or "centre of mass" in lower:
        positions = _ordered_values(cleaned, r"km|cm|mm|m|ft|yd|in|mi")
        if len(masses) != 2 or len(positions) != 2:
            # This operation deliberately starts with the common two-point
            # school form. A three-body or continuous-distribution question
            # belongs to a different input shape and must not be truncated.
            return None
        return PhysicsIntent(
            kind="momentum",
            physics_op="center_of_mass",
            physics_params={
                "m1": masses[0][0],
                "m2": masses[1][0],
                "x1": positions[0][0],
                "x2": positions[1][0],
            },
            physics_units={
                "m1": masses[0][1] or "kg",
                "m2": masses[1][1] or "kg",
                "x1": positions[0][1] or "m",
                "x2": positions[1][1] or "m",
            },
            operation="solve",
        )

    is_collision = (
        _COLLISION_SUBJECT_RE.search(cleaned) is not None or _INELASTIC_RE.search(lower) is not None
    )

    # --- 1D collision: two masses, at least one velocity ---
    if is_collision and len(masses) >= 2:
        # Only 1D conservation is implemented. Handing back the 1D number for a
        # 2D question is the same defect as the projectile answer it replaces,
        # just less obvious — the arithmetic is right for a problem nobody asked.
        if _TWO_DIMENSIONAL_RE.search(cleaned):
            return None
        elastic = _ELASTIC_RE.search(lower) is not None and not _INELASTIC_RE.search(lower)
        inelastic = _INELASTIC_RE.search(lower) is not None
        # Refuse rather than guess. Elastic and inelastic give genuinely
        # different answers from identical inputs, so an unstated collision type
        # would produce a confidently wrong number — the same failure mode the
        # tension guard closes off.
        if not elastic and not inelastic:
            return None
        m1, m1_unit = masses[0]
        m2, m2_unit = masses[1]
        v1, v1_unit = velocities[0] if velocities else (0.0, "m/s")
        # "hits a ball at rest" leaves v2 unwritten; "at rest" means zero.
        v2, v2_unit = velocities[1] if len(velocities) > 1 else (0.0, "m/s")
        return PhysicsIntent(
            kind="momentum",
            physics_op="final_velocity",
            physics_params={
                "m1": m1,
                "m2": m2,
                "v1": v1,
                "v2": v2,
                "elastic": 1.0 if elastic else 0.0,
            },
            physics_units={
                "m1": m1_unit or "kg",
                "m2": m2_unit or "kg",
                "v1": v1_unit or "m/s",
                "v2": v2_unit or "m/s",
                "elastic": "",
            },
            operation="solve",
        )

    # --- Impulse: J = F dt, or J = m (v2 - v1) ---
    if "impulse" in lower:
        forces = _ordered_values(cleaned, r"N")
        times = _ordered_values(cleaned, _MOMENTUM_TIME_UNITS)
        if forces and times:
            f, f_unit = forces[0]
            dt, dt_unit = times[0]
            return PhysicsIntent(
                kind="momentum",
                physics_op="impulse",
                physics_params={"F": f, "dt": dt},
                physics_units={"F": f_unit or "N", "dt": dt_unit or "s"},
                operation="solve",
            )
        if masses and len(velocities) >= 2:
            m, m_unit = masses[0]
            v1, v1_unit = velocities[0]
            v2, v2_unit = velocities[1]
            return PhysicsIntent(
                kind="momentum",
                physics_op="impulse",
                physics_params={"m": m, "v1": v1, "v2": v2},
                physics_units={"m": m_unit or "kg", "v1": v1_unit or "m/s", "v2": v2_unit or "m/s"},
                operation="solve",
            )
        return None

    # --- Plain momentum: p = m v ---
    if "momentum" in lower and masses and velocities:
        m, m_unit = masses[0]
        v, v_unit = velocities[0]
        return PhysicsIntent(
            kind="momentum",
            physics_op="momentum",
            physics_params={"m": m, "v": v},
            physics_units={"m": m_unit or "kg", "v": v_unit or "m/s"},
            operation="solve",
        )

    return None


_FRICTION_CUES = (
    "normal force",
    "frictionless",
)

_FRICTION_SUBJECT = r"friction|frictional|incline|inclined|ramp"

_FRICTION_GIVEN = r"coefficient|\bmu\s*(?:=|is)|\u03bc\s*(?:=|is)|\d+\s*(?:degrees?|deg|\u00b0)"

_FRICTION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"(?:{_FRICTION_SUBJECT}).{{0,80}}?(?:{_FRICTION_GIVEN})", re.IGNORECASE),
    re.compile(rf"(?:{_FRICTION_GIVEN}).{{0,80}}?(?:{_FRICTION_SUBJECT})", re.IGNORECASE),
    re.compile(
        r"\b(?:minimum|least|smallest)\s+(?:horizontal\s+)?force\b.{0,100}?"
        r"\b(?:mu|μ)\s*(?:=|is)\s*\d",
        re.IGNORECASE,
    ),
)

_FRICTION_FORCE_ASK_RE = re.compile(
    r"friction(?:al)?\s+force|force\s+of\s+friction"
    r"|(?:find|calculate|determine|compute|what\s+is)\s+the\s+friction\b",
    re.IGNORECASE,
)

_MU_RE = re.compile(
    r"(?:coefficient\s+of\s+(?:kinetic\s+|static\s+)?friction\s*(?:of|=|is)?\s*"
    r"|coefficient\s*(?:of|=|is)?\s*"
    r"|\bmu\s+is\s+|\bmu\s*=\s*|\u03bc\s+is\s+|\u03bc\s*=\s*)"
    r"(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_MU_ASK_RE = re.compile(
    r"(?:what|find|calculate|determine|compute)\b[^.?!]{0,40}?"
    r"\bcoefficient\s+of\s+(?:kinetic\s+|static\s+)?friction\b"
    r"|\bcoefficient\s+of\s+(?:kinetic\s+|static\s+)?friction\s*\?",
    re.IGNORECASE,
)

_SLIPPING_RE = re.compile(
    r"\bstarts?\s+to\s+(?:slide|slip|move)\b|\bbegins?\s+to\s+(?:slide|slip|move)\b"
    r"|\bslipping\s+begins?\b|\bjust\s+(?:slides?|slips?|begins)\b"
    r"|\bslides?\s+(?:at|when|down\s+a)\b|\bon\s+the\s+point\s+of\b"
    r"|\bjust\s+prevents?\s+(?:it\s+from\s+)?slid(?:e|ing)\b",
    re.IGNORECASE,
)

_MIN_FORCE_ASK_RE = re.compile(
    r"\bminimum\s+force\b|\bleast\s+force\b|\bsmallest\s+force\b"
    r"|\bforce\s+(?:is\s+)?(?:needed|required)\s+to\s+(?:start|move|push|pull|budge)\b"
    r"|\bforce\s+to\s+(?:start|move|push|pull|budge)\b",
    re.IGNORECASE,
)

_INCLINE_ANGLE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)(?![A-Za-z0-9])", re.IGNORECASE
)


def _extract_friction_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _FRICTION_CUES, _FRICTION_CUE_RES):
        return None
    if "net force" in lower:
        # A different quantity. The force extractor refuses it via
        # _UNSUPPORTED_FORCE_CONTEXT rather than guessing, which is right.
        return None
    if has_equation(_strip_param_assignments(_MU_RE.sub("", cleaned))):
        return None

    mass = _find_value_with_specific_unit(
        cleaned, r"kg|g|mg|lb|lbs|oz", ("mass", "block", "box", "crate", "object", "body")
    )

    frictionless = "frictionless" in lower
    mu_match = _MU_RE.search(cleaned)
    mu = 0.0 if frictionless else (float(mu_match.group(1)) if mu_match else None)

    angle_match = _INCLINE_ANGLE_RE.search(cleaned)
    angle = float(angle_match.group(1)) if angle_match else 0.0

    wants_normal = "normal force" in lower
    wants_acceleration = "acceleration" in lower or "accelerate" in lower
    wants_friction = _FRICTION_FORCE_ASK_RE.search(cleaned) is not None and not frictionless
    wants_coefficient = _MU_ASK_RE.search(cleaned) is not None
    wants_min_force = _MIN_FORCE_ASK_RE.search(cleaned) is not None

    op: Literal[
        "friction_force",
        "normal_force",
        "incline_acceleration",
        "friction_coefficient",
        "minimum_force",
    ]
    if wants_coefficient:
        # mu = tan(theta) holds only at the angle where it *starts* to slide.
        # On any other incline the angle says nothing about mu, so the slipping
        # wording is required rather than assumed.
        op = "friction_coefficient"
        if angle == 0.0 or mu is not None or not _SLIPPING_RE.search(cleaned):
            return None
    elif wants_min_force:
        op = "minimum_force"
        if mass is None or mu is None:
            return None
        if angle != 0.0:
            # On a slope the minimum force is mu*m*g*cos(t) + m*g*sin(t), a
            # different formula. Not solved here, so not guessed at either.
            return None
    elif wants_acceleration:
        op = "incline_acceleration"
        # No mass requirement here, and that is the point: a = g(sin t - mu cos t)
        # is mass-independent, which is the whole reason the incline result is
        # worth teaching. Demanding a mass would reject the textbook phrasing
        # ("a block on a frictionless 30 degree incline") that omits it.
        if mu is None:
            # Without a coefficient this is only solvable if it is stated to be
            # frictionless — otherwise the answer needs a number nobody gave.
            return None
        if angle == 0.0:
            # "acceleration" with no incline angle is an F = ma question, not
            # this one. Leave it for the force extractor.
            return None
    elif wants_normal:
        op = "normal_force"
        if mass is None:
            return None
        mu = mu if mu is not None else 0.0
    elif wants_friction:
        op = "friction_force"
        if mass is None or mu is None:
            return None
    else:
        return None

    params: dict[str, float] = {"angle": angle, "g": _detect_gravity(cleaned)}
    units: dict[str, str] = {
        "angle": "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg",
        "g": "m/s^2",
    }
    # For `friction_coefficient` mu is the answer, not a given, so there is
    # none to pass. Every other op has already refused a missing one above.
    if mu is not None:
        params["mu"] = mu
        units["mu"] = ""
    if mass is not None:
        params["m"] = mass[0]
        units["m"] = mass[1] or "kg"
    return PhysicsIntent(
        kind="friction",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


_TENSION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?=.*\btension\b)(?=.*\d\s*(?:kg|lbs?|oz)\b)"
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
    if not _has_cue(lower, (), _TENSION_CUE_RES):
        return None
    if any(word in lower for word in _UNSUPPORTED_TENSION_CONTEXT):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    masses = _ordered_values(cleaned, r"kg|lbs?|oz")
    if not masses:
        return None

    # --- Atwood: two masses sharing one pulley --------------------------------
    is_pair = "atwood" in lower or "pulley" in lower
    if is_pair and len(masses) >= 2:
        # The heavier mass descends, so ordering them here makes the sign of
        # the acceleration a property of the physics rather than of the
        # sentence. Its magnitude is what the question asks for either way.
        heavy, light = sorted((masses[0], masses[1]), key=lambda pair: pair[0], reverse=True)
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
    accel = _find_value_with_specific_unit(
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
    re.compile(
        r"(?=.*\b(?:resolv\w*|components?)\b)(?=.*\d\s*N\b)(?=.*\d\s*(?:degrees?|deg|°))",
        re.IGNORECASE | re.DOTALL,
    ),
)

_PERPENDICULAR_RE = re.compile(
    r"\bperpendicular\b|\bright angles?\b|\bat 90\s*(?:degrees?|deg|°)"
    r"|\b(?:north|south)\b.{0,60}?\b(?:east|west)\b|\b(?:east|west)\b.{0,60}?\b(?:north|south)\b"
    r"|\bhorizontal\b.{0,60}?\bvertical\b|\bvertical\b.{0,60}?\bhorizontal\b",
    re.IGNORECASE,
)

_ANGLE_BETWEEN_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|°)(?:[^.]{0,40}?"
    r"(?:to each other|between them|apart|to one another))",
    re.IGNORECASE,
)

_ANGLE_VALUE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|°)(?![A-Za-z0-9])", re.IGNORECASE
)

_RESOLVE_RE = re.compile(r"\bresolv\w*\b|\bcomponents?\b", re.IGNORECASE)


def _extract_vector_force_intent(cleaned: str) -> PhysicsIntent | None:
    if not _has_cue(cleaned.lower(), (), _VECTOR_FORCE_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    forces = _ordered_values(cleaned, r"N")

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

    # --- one force split into components ------------------------------------
    if _RESOLVE_RE.search(cleaned) and forces:
        angle = _ANGLE_VALUE_RE.search(cleaned)
        if angle is None:
            return None
        return PhysicsIntent(
            kind="force",
            physics_op="resolve_force",
            physics_params={"F": forces[0][0], "angle": float(angle.group(1))},
            physics_units={"F": forces[0][1] or "N", "angle": "deg"},
            operation="solve",
        )

    return None


_FORCE_CUES = (
    "net force",
    "newton's second law",
    "newtons second law",
    "force of",
    "force required",
    "what is the force",
    "what's the force",
    "find the force",
    "find the mass",
    "acceleration given",
    "given force",
    # Question-first and verb-first shapes ("what force accelerates 5 kg...",
    # "calculate the force on a 5 kg object"). solve_force still needs exactly
    # two of F, m, a with units, so a non-physics "force" sentence returns None.
    "what force",
    "how much force",
    "force needed",
    "force on",
    "force acts",
    "force applied",
    "accelerates at",
    "accelerating at",
    "accelerated at",
)

_UNSUPPORTED_FORCE_CONTEXT = (
    "tension",
    "friction",
    "coefficient",
    "incline",
    "ramp",
    "slope",
    "pulley",
    "normal force",
    "spring",
    "centripetal",
    "buoyan",
)

_FORCE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:find|calculate|determine|compute)\s+f\b(?!\s*\()"),
)


def _extract_force_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _FORCE_CUES, _FORCE_CUE_RES):
        return None
    if any(word in lower for word in _UNSUPPORTED_FORCE_CONTEXT):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    # Mass (m): "mass of 5 kg", "5 kg mass", "5kg object" — use unit-specific
    # search so "20 N" (force) isn't picked up as the mass.
    mass: float | None = None
    mass_unit = "kg"
    mu = _find_value_with_specific_unit(
        cleaned,
        r"kg|g|mg|lb|lbs|oz",
        ("mass", "object", "body"),
    )
    if mu is not None:
        mass, mass_unit = mu

    # Force (F): "force of 20 N", "20 N force" — use unit-specific search.
    force: float | None = None
    force_unit = "N"
    fu = _find_value_with_specific_unit(cleaned, r"N", ("force",))
    if fu is not None:
        force, force_unit = fu

    # Acceleration (a): "acceleration of 2 m/s^2"
    accel: float | None = None
    accel_unit = "m/s^2"
    au = _find_value_with_specific_unit(
        cleaned,
        r"m/s\^?2|m/s2",
        ("acceleration", "accelerates", "accelerated"),
    )
    if au is not None:
        accel, accel_unit = au

    # Need at least two of (mass, force, accel) to solve F = ma.
    known = [v for v in (mass, force, accel) if v is not None]
    if len(known) < 2:
        return None

    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if mass is not None:
        params["m"] = mass
        units["m"] = mass_unit or "kg"
    if force is not None:
        params["F"] = force
        units["F"] = force_unit or "N"
    if accel is not None:
        params["a"] = accel
        units["a"] = accel_unit or "m/s^2"

    return PhysicsIntent(
        kind="force",
        physics_op="net_force",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


_ENERGY_CUES = (
    "kinetic energy",
    "potential energy",
    "work done",
    "work is done",
    "how much work",
    "work of",
    "power of",
    "what is the power",
    "what is its power",
    "what's the power",
    "what's its power",
    "energy of",
    "what power",
    "how much power",
    "find the power",
    "find its power",
    "calculate the power",
    "power needed",
    "power required",
    "power is needed",
    "mechanical efficiency",
    "machine efficiency",
    "efficiency of a machine",
)

_KE_ABBREV_RE = re.compile(r"\bk\.?\s?e\.?\s+of\b")

_PE_ABBREV_RE = re.compile(r"\bp\.?\s?e\.?\s+of\b")

_ENERGY_CUE_RES: tuple[re.Pattern[str], ...] = (_KE_ABBREV_RE, _PE_ABBREV_RE)


def _has_work_angle(text: str) -> bool:
    """True when work is at an angle (W = Fd cos θ) — unsupported."""
    lower = text.lower()
    return "degrees" in lower or "at an angle" in lower or "°" in text


def _extract_energy_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _ENERGY_CUES, _ENERGY_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    # A machine's useful energy output divided by its energy input. Thermal
    # engines retain their own W/Q_in operation in the earlier thermal
    # extractor; this branch owns explicitly mechanical/machine wording.
    if "efficiency" in lower:
        if not any(word in lower for word in ("machine", "mechanical", "device", "motor")):
            return None
        energies = _ordered_values(cleaned, r"kilojoules?|joules?|kJ|J")
        if len(energies) != 2:
            return None
        output_match = re.search(
            rf"(?:output|outputs|useful(?:\s+energy)?)\D{{0,24}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        input_match = re.search(
            rf"(?:input|supplied|receives?|takes?\s+in)\D{{0,24}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        output_reverse = re.search(
            rf"({_NUMBER})\s*(kilojoules?|joules?|kJ|J)\s*(?:output|useful)",
            cleaned,
            re.IGNORECASE,
        )
        input_reverse = re.search(
            rf"({_NUMBER})\s*(kilojoules?|joules?|kJ|J)\s*(?:input|supplied)",
            cleaned,
            re.IGNORECASE,
        )

        def _labelled_energy(
            forward: re.Match[str] | None, reverse: re.Match[str] | None
        ) -> tuple[float, str] | None:
            match = forward or reverse
            return None if match is None else (float(match.group(1)), match.group(2))

        output = _labelled_energy(output_match, output_reverse)
        supplied = _labelled_energy(input_match, input_reverse)
        if output is None or supplied is None:
            # Numeric order alone is not a safe way to infer input vs output.
            return None
        return PhysicsIntent(
            kind="energy",
            physics_op="mechanical_efficiency",
            physics_params={"E_out": output[0], "E_in": supplied[0]},
            physics_units={"E_out": output[1] or "J", "E_in": supplied[1] or "J"},
            operation="solve",
        )

    # Mass (m) — use unit-specific search so force isn't picked up as mass.
    mass: float | None = None
    mass_unit = "kg"
    mu = _find_value_with_specific_unit(
        cleaned,
        r"kg|g|mg|lb|lbs|oz",
        ("mass", "object", "body"),
    )
    if mu is not None:
        mass, mass_unit = mu

    # Velocity (v) — for KE = 1/2 m v^2
    velocity: float | None = None
    vel_unit = "m/s"
    vu = _find_value_with_specific_unit(
        cleaned,
        r"m/s|km/h|mph|cm/s|mm/s",
        ("velocity", "speed", "moving", "traveling", "travelling"),
    )
    if vu is not None:
        velocity, vel_unit = vu

    # Height (h) — for PE = m g h. Use length-specific search.
    height: float | None = None
    height_unit = "m"
    hu = _find_value_with_specific_unit(
        cleaned,
        r"km|cm|mm|m|ft|yd|in|mi",
        ("height", "high", "above"),
    )
    if hu is not None:
        height, height_unit = hu

    # Force (F) — for W = F d
    force: float | None = None
    force_unit = "N"
    fu = _find_value_with_specific_unit(cleaned, r"\bN\b", ("force",))
    if fu is not None:
        force, force_unit = fu

    # Distance (d) — for W = F d. Use length-specific search.
    distance: float | None = None
    dist_unit = "m"
    du = _find_value_with_specific_unit(
        cleaned,
        r"km|cm|mm|m|ft|yd|in|mi",
        ("distance", "over", "through"),
    )
    if du is not None:
        distance, dist_unit = du

    # Energy done (W, in joules) and elapsed time — for P = W / t.
    work_done: float | None = None
    work_unit = "J"
    wu = _find_value_with_specific_unit(cleaned, r"kilojoules?|joules?|kJ|J", ("work", "energy"))
    if wu is not None:
        work_done, work_unit = wu

    elapsed: float | None = None
    elapsed_unit = "s"
    tu = _find_value_with_specific_unit(
        cleaned,
        r"milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h",
    )
    if tu is not None:
        elapsed, elapsed_unit = tu

    # Decide the operation. Power is checked before work because a question
    # naming both ("what power does 100 J of work in 5 s need") is asking for
    # the power; "work done by a 10 N force" names only work and is unaffected.
    op: Literal["kinetic_energy", "potential_energy", "work", "power"]
    if "kinetic energy" in lower or _KE_ABBREV_RE.search(lower):
        op = "kinetic_energy"
        if mass is None or velocity is None:
            return None
    elif "potential energy" in lower or _PE_ABBREV_RE.search(lower):
        op = "potential_energy"
        if mass is None or height is None:
            return None
    elif "power" in lower:
        op = "power"
        # Either school form: P = F v, or P = W / t.
        if (force is None or velocity is None) and (work_done is None or elapsed is None):
            return None
    elif "work" in lower:
        # W = Fd cos θ is unsupported — same refusal as friction/tension.
        if _has_work_angle(cleaned):
            return None
        op = "work"
        if force is None or distance is None:
            return None
    else:
        # "energy of" / "conservation of energy" — pick whichever we can solve.
        if mass is not None and velocity is not None:
            op = "kinetic_energy"
        elif mass is not None and height is not None:
            op = "potential_energy"
        elif force is not None and distance is not None:
            if _has_work_angle(cleaned):
                return None
            op = "work"
        else:
            return None

    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if op in ("kinetic_energy", "potential_energy") and mass is not None:
        params["m"] = mass
        units["m"] = mass_unit or "kg"
    if op in ("kinetic_energy", "power") and velocity is not None:
        params["v"] = velocity
        units["v"] = vel_unit or "m/s"
    if op == "potential_energy" and height is not None:
        params["h"] = height
        units["h"] = height_unit or "m"
    if op == "power" and (force is None or velocity is None):
        # P = W / t. Drop any partial F/v so solve_energy picks this form.
        params.pop("v", None)
        units.pop("v", None)
        if work_done is not None and elapsed is not None:
            params["W"] = work_done
            units["W"] = work_unit or "J"
            params["t"] = elapsed
            units["t"] = elapsed_unit or "s"
    elif op in ("work", "power") and force is not None:
        params["F"] = force
        units["F"] = force_unit or "N"
    if op == "work" and distance is not None:
        params["d"] = distance
        units["d"] = dist_unit or "m"
    if op == "potential_energy":
        params["g"] = _detect_gravity(cleaned)
        units["g"] = "m/s^2"

    return PhysicsIntent(
        kind="energy",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )
