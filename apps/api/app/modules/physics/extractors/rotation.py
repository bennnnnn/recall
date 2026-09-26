"""Circular-motion, torque, and rotational-mechanics extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _has_cue,
    _positioned_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.mechanics import _INCLINE_ANGLE_RE, _MASS_UNITS
from app.modules.physics.extractors.oscillations_waves import _ANGULAR_FREQ_RE
from app.services.text_match import has_equation

_ROTATION_CUES = (
    "moment of inertia",
    "rotational inertia",
    "angular momentum",
    "rotational kinetic energy",
    "angular acceleration",
)

_INERTIA_PATTERN = r"kg\s*m\^?2|kg\s*\*\s*m\^?2|kilogram\s+met(?:er|re)\s+squared"

_ROTATION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\d\s*(?:{_INERTIA_PATTERN})", re.IGNORECASE),
    re.compile(r"\bangular\s+(?:velocity|speed)\b.{0,80}?\d\s*(?:radians?|rad)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:radians?|rad)\b.{0,80}?\bangular\s+(?:velocity|speed)\b", re.IGNORECASE),
)

_INERTIA_SHAPES: dict[str, tuple[float, str]] = {
    "hoop": (1.0, "m r^2"),
    "ring": (1.0, "m r^2"),
    "cylindrical shell": (1.0, "m r^2"),
    "disc": (0.5, r"\tfrac{1}{2} m r^2"),
    "disk": (0.5, r"\tfrac{1}{2} m r^2"),
    "solid cylinder": (0.5, r"\tfrac{1}{2} m r^2"),
    "solid sphere": (0.4, r"\tfrac{2}{5} m r^2"),
    "hollow sphere": (2 / 3, r"\tfrac{2}{3} m r^2"),
    "spherical shell": (2 / 3, r"\tfrac{2}{3} m r^2"),
}


def _extract_rotation_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _ROTATION_CUES, _ROTATION_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    inertia = _find_value_with_specific_unit(cleaned, _INERTIA_PATTERN)
    omega = _ANGULAR_FREQ_RE.search(cleaned)
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )

    if "moment of inertia" in lower or "rotational inertia" in lower:
        shape = next(
            ((k, name) for name, (k, _) in _INERTIA_SHAPES.items() if name in lower),
            None,
        )
        formula = next((tex for name, (_, tex) in _INERTIA_SHAPES.items() if name in lower), None)
        if shape is None or formula is None or mass is None or radius is None:
            return None
        return PhysicsIntent(
            kind="rotation",
            physics_op="moment_of_inertia",
            physics_params={"m": mass[0], "r": radius[0], "shape_factor": shape[0]},
            physics_units={"m": mass[1] or "kg", "r": radius[1] or "m", "shape_factor": ""},
            operation="solve",
        )

    if inertia is not None and omega is not None:
        op = (
            "rotational_kinetic_energy"
            if "kinetic energy" in lower or "rotational energy" in lower
            else "angular_momentum"
        )
        return PhysicsIntent(
            kind="rotation",
            physics_op=op,  # type: ignore[arg-type]
            physics_params={"inertia": inertia[0], "omega": float(omega.group(1))},
            physics_units={"inertia": "kg*m^2", "omega": "rad/s"},
            operation="solve",
        )

    # omega = theta / t
    turned = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:radians?|rad)\b", cleaned, re.IGNORECASE)
    elapsed = _find_value_with_specific_unit(cleaned, r"seconds?|secs?|sec|s|minutes?|mins?|min")
    if turned is not None and elapsed is not None:
        return PhysicsIntent(
            kind="rotation",
            physics_op="angular_velocity",
            physics_params={"theta": float(turned.group(1)), "t": elapsed[0]},
            physics_units={"theta": "rad", "t": elapsed[1] or "s"},
            operation="solve",
        )
    return None


_CIRCULAR_CUES = (
    "centripetal",
    "circular motion",
    "orbital",
    "revolution",
)

_ANGULAR_ASK_RE = re.compile(r"\bangular\s+(?:velocity|speed|frequency)\b", re.IGNORECASE)

_RPM_RE = re.compile(rf"({_NUMBER})\s*(?:rpm|revolutions?\s+per\s+minute)\b", re.IGNORECASE)

_CIRCULAR_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bperiod\b.{0,80}?\bradius\b", re.IGNORECASE),
    re.compile(r"\bradius\b.{0,80}?\bperiod\b", re.IGNORECASE),
    re.compile(
        r"\bangular\s+(?:velocity|speed)\b.{0,80}?\b(?:radius|circular|circle|track|orbit)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:radius|circular|circle|track|orbit)\b.{0,80}?\bangular\s+(?:velocity|speed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:rotates?|spins?|turns?)\b.{0,80}?\d\s*(?:rpm|revolutions?\s+per\s+minute)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bomega\s*=?.{0,30}?\brad(?:ians?)?/s\b.{0,80}?\bradius\b", re.IGNORECASE),
)


def _extract_circular_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _CIRCULAR_CUES, _CIRCULAR_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    rpm_match = _RPM_RE.search(cleaned)
    if rpm_match is not None and _ANGULAR_ASK_RE.search(cleaned):
        return PhysicsIntent(
            kind="circular",
            physics_op="angular_velocity",
            physics_params={"rpm": float(rpm_match.group(1))},
            physics_units={"rpm": ""},
            operation="solve",
        )

    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    omega = _ANGULAR_FREQ_RE.search(cleaned)
    if radius is None or (speed is None and omega is None):
        return None

    mass = _find_value_with_specific_unit(
        cleaned, r"kg|g|mg|lb|lbs|oz", ("mass", "object", "body", "ball", "car")
    )

    op: Literal[
        "centripetal_force",
        "centripetal_acceleration",
        "orbital_period",
        "angular_velocity",
    ]
    if _ANGULAR_ASK_RE.search(cleaned):
        # Before "period": "angular frequency" contains neither word, but
        # "what angular velocity gives a period of 2 s" contains both.
        op = "angular_velocity"
    elif "period" in lower or "revolution" in lower:
        op = "orbital_period"
    elif "acceleration" in lower:
        op = "centripetal_acceleration"
    elif "force" in lower:
        op = "centripetal_force"
        # F = m v^2 / r is the only one of the three that needs a mass; the
        # other two are mass-independent, same as the incline result in P5.
        if mass is None:
            return None
    else:
        return None

    params: dict[str, float] = {"r": radius[0]}
    units: dict[str, str] = {"r": radius[1] or "m"}
    if speed is not None:
        params["v"] = speed[0]
        units["v"] = speed[1] or "m/s"
    elif omega is not None:
        params["omega"] = float(omega.group(1))
        units["omega"] = "rad/s"
    if mass is not None:
        params["m"] = mass[0]
        units["m"] = mass[1] or "kg"
    return PhysicsIntent(
        kind="circular",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


_TORQUE_CUES = (
    "torque",
    "pivot",
    "fulcrum",
    "lever arm",
    "see-saw",
    "seesaw",
)

_PIVOT_WORDS = r"pivot|fulcrum|lever|see-?saw|balance"

_TORQUE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\bmoments?\b.{{0,80}}?(?:{_PIVOT_WORDS})", re.IGNORECASE),
    re.compile(rf"(?:{_PIVOT_WORDS}).{{0,80}}?\bmoments?\b", re.IGNORECASE),
    re.compile(r"\blever\b", re.IGNORECASE),
)

_TORQUE_UNSUPPORTED = ("moment of inertia", "angular momentum", "rotational inertia")

_TORQUE_VALUE_RE = re.compile(
    rf"({_NUMBER})\s*(?:N|newtons?)\s*(?:[·*]\s*)?(?:m|met(?:er|re)s?)(?![A-Za-z0-9/^])",
    re.IGNORECASE,
)

_PLAIN_FORCE_RE = re.compile(
    rf"({_NUMBER})\s*(N|newtons?)(?!\s*(?:[·*]\s*)?(?:m|met(?:er|re)s?)\b)",
    re.IGNORECASE,
)


def _extract_torque_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _TORQUE_CUES, _TORQUE_CUE_RES):
        return None
    if any(word in lower for word in _TORQUE_UNSUPPORTED):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    torque_values = [
        (match.start(), float(match.group(1))) for match in _TORQUE_VALUE_RE.finditer(cleaned)
    ]
    if len(torque_values) >= 2 and (
        "clockwise" in lower or "counterclockwise" in lower or "anticlockwise" in lower
    ):
        direction_marks = [
            (match.start(), -1.0 if match.group(1).lower() == "clockwise" else 1.0)
            for match in re.finditer(
                r"\b(clockwise|counterclockwise|anticlockwise)\b", cleaned, re.I
            )
        ]
        if not direction_marks:
            return None
        clause_spans: list[tuple[int, int, float]] = []
        clause_start = 0
        for separator in re.finditer(r"\b(?:against|versus|vs\.?)\b", cleaned, re.I):
            clause = cleaned[clause_start : separator.start()]
            direction = re.search(r"\b(clockwise|counterclockwise|anticlockwise)\b", clause, re.I)
            if direction is not None:
                clause_spans.append(
                    (
                        clause_start,
                        separator.start(),
                        -1.0 if direction.group(1).lower() == "clockwise" else 1.0,
                    )
                )
            clause_start = separator.end()
        final_clause = cleaned[clause_start:]
        final_direction = re.search(
            r"\b(clockwise|counterclockwise|anticlockwise)\b", final_clause, re.I
        )
        if final_direction is not None:
            clause_spans.append(
                (
                    clause_start,
                    len(cleaned),
                    -1.0 if final_direction.group(1).lower() == "clockwise" else 1.0,
                )
            )
        signed: list[float] = []
        for position, value in torque_values:
            clause_sign = next(
                (sign for start, end, sign in clause_spans if start <= position < end),
                None,
            )
            if clause_sign is None:
                _, clause_sign = min(direction_marks, key=lambda item: abs(item[0] - position))
            signed.append(clause_sign * value)
        return PhysicsIntent(
            kind="torque",
            physics_op="net_torque",
            physics_params={f"tau{index}": value for index, value in enumerate(signed, start=1)},
            physics_units={f"tau{index}": "N*m" for index in range(1, len(signed) + 1)},
            operation="solve",
        )

    plain_forces = [
        (match.start(), float(match.group(1)), match.group(2))
        for match in _PLAIN_FORCE_RE.finditer(cleaned)
    ]
    if (
        len(torque_values) == 1
        and len(plain_forces) == 1
        and re.search(
            r"\b(?:lever arm|perpendicular distance|distance from (?:the )?pivot)\b", cleaned, re.I
        )
    ):
        return PhysicsIntent(
            kind="torque",
            physics_op="lever_arm",
            physics_params={"tau": torque_values[0][1], "F": plain_forces[0][1]},
            physics_units={"tau": "N*m", "F": plain_forces[0][2] or "N"},
            operation="solve",
        )

    placed_masses = _positioned_values(cleaned, _MASS_UNITS)
    placed_distances = _positioned_values(cleaned, _LENGTH_UNIT_PATTERN)
    balancing = "balance" in lower or "see-saw" in lower or "seesaw" in lower
    if balancing and len(placed_masses) >= 2 and placed_distances:
        d_pos, d_val, d_unit = placed_distances[0]
        preceding = [mass for mass in placed_masses if mass[0] < d_pos]
        known = preceding[-1] if preceding else placed_masses[0]
        others = [mass for mass in placed_masses if mass[0] != known[0]]
        if not others:
            return None
        unknown = others[0]
        return PhysicsIntent(
            kind="torque",
            physics_op="moment_balance",
            physics_params={"m1": known[1], "d1": d_val, "m2": unknown[1]},
            physics_units={
                "m1": known[2] or "kg",
                "d1": d_unit or "m",
                "m2": unknown[2] or "kg",
            },
            operation="solve",
        )

    placed_forces = _positioned_values(cleaned, r"N")
    placed_distances = _positioned_values(cleaned, _LENGTH_UNIT_PATTERN)
    if not placed_forces or not placed_distances:
        return None

    # Two forces and one distance is the classic balance question. Pair the
    # distance with the force it actually belongs to rather than taking them in
    # written order: "the distance for a 10 N force to balance a 5 N force at
    # 2 m" mentions the 10 N first, but the 2 m is the *5 N* force's arm.
    # Written order answers 4 m there; the true answer is 1 m.
    if balancing and len(placed_forces) >= 2:
        d_pos, d_val, d_unit = placed_distances[0]
        preceding = [f for f in placed_forces if f[0] < d_pos]
        # The force nearest *before* the distance owns it; the remaining force
        # is the one whose arm we are solving for.
        known = preceding[-1] if preceding else placed_forces[0]
        others = [f for f in placed_forces if f[0] != known[0]]
        if not others:
            return None
        unknown = others[0]
        return PhysicsIntent(
            kind="torque",
            physics_op="moment_balance",
            physics_params={"F1": known[1], "d1": d_val, "F2": unknown[1]},
            physics_units={
                "F1": known[2] or "N",
                "d1": d_unit or "m",
                "F2": unknown[2] or "N",
            },
            operation="solve",
        )
    # One known force and two stated arms asks for the balancing force rather
    # than another arm. The known force owns the first arm stated after it;
    # this also handles question-first wording where the unknown arm comes
    # before the known force ("force at 4 m balances 50 N at 2 m").
    if balancing and len(placed_forces) == 1 and len(placed_distances) >= 2:
        known_force = placed_forces[0]
        following = [distance for distance in placed_distances if distance[0] > known_force[0]]
        known_distance = (
            min(following, key=lambda distance: distance[0])
            if following
            else min(
                placed_distances,
                key=lambda distance: abs(distance[0] - known_force[0]),
            )
        )
        unknown_distances = [
            distance for distance in placed_distances if distance[0] != known_distance[0]
        ]
        if not unknown_distances:
            return None
        unknown_distance = unknown_distances[0]
        return PhysicsIntent(
            kind="torque",
            physics_op="moment_balance",
            physics_params={
                "F1": known_force[1],
                "d1": known_distance[1],
                "d2": unknown_distance[1],
            },
            physics_units={
                "F1": known_force[2] or "N",
                "d1": known_distance[2] or "m",
                "d2": unknown_distance[2] or "m",
            },
            operation="solve",
        )
    forces = [(f[1], f[2]) for f in placed_forces]
    distances = [(d[1], d[2]) for d in placed_distances]

    angle_match = _INCLINE_ANGLE_RE.search(cleaned)
    params: dict[str, float] = {"F": forces[0][0], "d": distances[0][0]}
    units: dict[str, str] = {"F": forces[0][1] or "N", "d": distances[0][1] or "m"}
    if angle_match:
        params["angle"] = float(angle_match.group(1))
        units["angle"] = "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg"
    return PhysicsIntent(
        kind="torque",
        physics_op="torque",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )
