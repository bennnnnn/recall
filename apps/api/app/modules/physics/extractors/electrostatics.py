"""Electrostatics: Coulomb's law between two charges."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.circuit_patterns import _COULOMB_PATTERN
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.cues import (
    _has_cue_either_case,
)
from app.modules.physics.extractors.school_extensions import blocks_field
from app.services.text_match import has_equation

_ELECTROSTATICS_CUES = (
    "electrostatic",
    "electric force",
    "coulomb force",
    "coulomb's law",
    "coulomb law",
    "point charge",
    "electric field",
    "electric potential",
    "electric potential energy",
)

_TWO_CHARGES_RE = re.compile(r"\btwo\s+(?:point\s+)?charges?\b", re.IGNORECASE)

_ELECTROSTATICS_CUE_RES: tuple[re.Pattern[str], ...] = (_TWO_CHARGES_RE,)


def _extract_electrostatics_intent(cleaned: str) -> PhysicsIntent | None:
    if not _has_cue_either_case(cleaned, _ELECTROSTATICS_CUES, _ELECTROSTATICS_CUE_RES):
        return None
    if blocks_field(cleaned):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None
    lower = cleaned.lower()
    charges = _ordered_values(cleaned, _COULOMB_PATTERN)
    if len(charges) == 1 and "each" in lower and _TWO_CHARGES_RE.search(cleaned):
        charges = [charges[0], charges[0]]
    separation = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("separated", "separation", "apart", "distance", "from"),
        require_keyword=True,
    )
    if separation is None or separation[0] <= 0:
        return None

    if "potential energy" in lower:
        if len(charges) != 2:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="electric_potential_energy",
            physics_params={"q1": charges[0][0], "q2": charges[1][0], "r": separation[0]},
            physics_units={
                "q1": charges[0][1] or "C",
                "q2": charges[1][1] or "C",
                "r": separation[1] or "m",
            },
            operation="solve",
        )

    if "electric field" in lower:
        if len(charges) != 1:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="electric_field",
            physics_params={"Q": charges[0][0], "r": separation[0]},
            physics_units={"Q": charges[0][1] or "C", "r": separation[1] or "m"},
            operation="solve",
        )

    if "electric potential" in lower:
        if len(charges) != 1:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="electric_potential",
            physics_params={"Q": charges[0][0], "r": separation[0]},
            physics_units={"Q": charges[0][1] or "C", "r": separation[1] or "m"},
            operation="solve",
        )

    if ("force" not in lower and "coulomb" not in lower) or len(charges) != 2:
        return None

    return PhysicsIntent(
        kind="magnetism",
        physics_op="electric_force",
        physics_params={"q1": charges[0][0], "q2": charges[1][0], "r": separation[0]},
        physics_units={
            "q1": charges[0][1] or "C",
            "q2": charges[1][1] or "C",
            "r": separation[1] or "m",
        },
        operation="solve",
    )
