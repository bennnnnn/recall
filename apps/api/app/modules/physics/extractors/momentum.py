"""Momentum extractors: collisions, impulse, centre of mass, p = mv."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _MASS_UNITS,
    _VELOCITY_UNIT_PATTERN,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.cues import (
    _has_cue,
)
from app.services.text_match import has_equation

_MOMENTUM_CUES = (
    "center of mass",
    "centre of mass",
    "elastically",
    "inelastically",
    "stick together",
    "sticks together",
)

# "The stock has momentum, up 12 percent" and "a three-car collision" are
# English. These words mean mechanics beside a mass, a velocity or a force.
_MOMENTUM_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\A(?=.*\b(?:momentum|impulse|collisions?|collid(?:e|es|ed|ing)|recoil(?:s|ed)?)\b)"
        r"(?=.*\d\s*(?:kg|g|grams?|m/s|km/h|mph|cm/s|N|newtons?|N\s*[·*]?\s*s)(?![A-Za-z0-9/]))",
        re.IGNORECASE | re.DOTALL,
    ),
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

_MOMENTUM_TIME_UNITS = r"milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"

# The second speed points back the way the body came: "hits a wall at 10 m/s
# and rebounds at 8 m/s" is +10 then -8. Read as two forward speeds, the
# impulse came out -0.4 N·s instead of 3.6 N·s.
_REVERSAL_RE = re.compile(
    r"\b(?:rebound(?:s|ed|ing)?|bounc(?:es|ed|ing|e)\s+(?:back|off)|reverses?|reversed"
    r"|opposite\s+direction|comes?\s+back|returns?\s+at|back\s+at)\b",
    re.IGNORECASE,
)


def _extract_momentum_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _MOMENTUM_CUES, _MOMENTUM_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    masses = _ordered_values(cleaned, _MASS_UNITS)
    velocities = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)

    # --- Centre of mass: x_cm = sum(m_i x_i) / sum(m_i) ---------------
    if "center of mass" in lower or "centre of mass" in lower:
        positions = _ordered_values(cleaned, r"km|cm|mm|m|ft|yd|in|mi")
        if len(masses) == 3 and len(positions) == 3:
            return PhysicsIntent(
                kind="momentum",
                physics_op="center_of_mass_three",
                physics_params={
                    "m1": masses[0][0],
                    "m2": masses[1][0],
                    "m3": masses[2][0],
                    "x1": positions[0][0],
                    "x2": positions[1][0],
                    "x3": positions[2][0],
                },
                physics_units={
                    "m1": masses[0][1] or "kg",
                    "m2": masses[1][1] or "kg",
                    "m3": masses[2][1] or "kg",
                    "x1": positions[0][1] or "m",
                    "x2": positions[1][1] or "m",
                    "x3": positions[2][1] or "m",
                },
                operation="solve",
            )
        if len(masses) != 2 or len(positions) != 2:
            # Two and three stated point masses are closed. A fourth mass or a
            # continuous distribution is a different shape and must not be truncated.
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
            if _REVERSAL_RE.search(cleaned) and v1 * v2 > 0:
                v2 = -v2
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
