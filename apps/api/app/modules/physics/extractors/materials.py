"""Materials extractors: stress, strain, Young's modulus."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _find_value_with_specific_unit,
    _has_cue,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.fluid_readings import _AREA_PATTERN, _PRESSURE_PATTERN
from app.services.text_match import has_equation

_MATERIALS_CUES = ("young's modulus", "youngs modulus", "young modulus", "tensile stress")

_MATERIALS_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bstress\b.{{0,80}}?\d\s*(?:N|newtons?|{_PRESSURE_PATTERN})(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:N|newtons?|{_PRESSURE_PATTERN})(?![A-Za-z0-9]).{{0,80}}?\bstress\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bstrain\b.{{0,80}}?\d\s*(?:{_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9])", re.IGNORECASE
    ),
    re.compile(
        rf"\d\s*(?:{_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9]).{{0,80}}?\bstrain\b", re.IGNORECASE
    ),
)


def _extract_materials_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _MATERIALS_CUES, _MATERIALS_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    stress = _find_value_with_specific_unit(cleaned, _PRESSURE_PATTERN)
    strain_match = re.search(rf"strain\s*(?:of|is|=)?\s*({_NUMBER})", cleaned, re.IGNORECASE)
    force = _find_value_with_specific_unit(cleaned, r"N|newtons?", ("force", "load"))
    area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN)
    original = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("wire", "rod", "bar", "long", "length", "original")
    )
    extension = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("extends", "extension", "stretches", "lengthens", "elongat"),
    )

    if "modulus" in lower:
        if stress is None or strain_match is None:
            return None
        return PhysicsIntent(
            kind="materials",
            physics_op="youngs_modulus",
            physics_params={"sigma": stress[0], "strain": float(strain_match.group(1))},
            physics_units={"sigma": stress[1] or "Pa", "strain": ""},
            operation="solve",
        )

    if "strain" in lower:
        # Two distinct lengths, not one read twice. "a wire extends by 4 mm"
        # matches both keyword sets on the same value, which would give a
        # strain of exactly 1 for any wire.
        lengths = _ordered_values(cleaned, _LENGTH_UNIT_PATTERN)
        if len(lengths) == 2:
            original, extension = lengths
        if original is None or extension is None or len(lengths) < 2:
            return None
        if original[0] == extension[0]:
            return None
        return PhysicsIntent(
            kind="materials",
            physics_op="strain",
            physics_params={"L0": original[0], "dL": extension[0]},
            physics_units={"L0": original[1] or "m", "dL": extension[1] or "m"},
            operation="solve",
        )

    if force is not None and area is not None:
        return PhysicsIntent(
            kind="materials",
            physics_op="stress",
            physics_params={"F": force[0], "area": area[0]},
            physics_units={"F": force[1] or "N", "area": area[1] or "m^2"},
            operation="solve",
        )
    return None
