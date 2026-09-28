"""Canonical registry of verified physics operations.

Law name, base equation, result symbol, and assumptions are read from here.
``PhysicsIntent.physics_op`` stays the schema mirror; a test keeps the two sets
identical.
"""

from __future__ import annotations

from app.modules.physics.catalog.circuit import SPECS as CIRCUIT
from app.modules.physics.catalog.circular import SPECS as CIRCULAR
from app.modules.physics.catalog.energy import SPECS as ENERGY
from app.modules.physics.catalog.fluids import SPECS as FLUIDS
from app.modules.physics.catalog.force import SPECS as FORCE
from app.modules.physics.catalog.friction import SPECS as FRICTION
from app.modules.physics.catalog.gravitation import SPECS as GRAVITATION
from app.modules.physics.catalog.kinematics import SPECS as KINEMATICS
from app.modules.physics.catalog.magnetism import SPECS as MAGNETISM
from app.modules.physics.catalog.materials import SPECS as MATERIALS
from app.modules.physics.catalog.modern import SPECS as MODERN
from app.modules.physics.catalog.momentum import SPECS as MOMENTUM
from app.modules.physics.catalog.optics import SPECS as OPTICS
from app.modules.physics.catalog.projectile import SPECS as PROJECTILE
from app.modules.physics.catalog.rotation import SPECS as ROTATION
from app.modules.physics.catalog.spec import (
    FormulaSpec,
    formula,
    matching_variant,
    select_formula,
    symbol_for,
    variable_for,
    visible_assumptions,
)
from app.modules.physics.catalog.spring import SPECS as SPRING
from app.modules.physics.catalog.suvat import SPECS as SUVAT
from app.modules.physics.catalog.thermal import SPECS as THERMAL
from app.modules.physics.catalog.torque import SPECS as TORQUE
from app.modules.physics.catalog.waves import SPECS as WAVES

__all__ = [
    "CATALOG",
    "FormulaSpec",
    "formula",
    "formula_spec",
    "matching_variant",
    "select_formula",
    "symbol_for",
    "variable_for",
    "visible_assumptions",
]


def _register(*groups: tuple[FormulaSpec, ...]) -> dict[str, FormulaSpec]:
    catalog: dict[str, FormulaSpec] = {}
    for group in groups:
        for spec in group:
            if spec.id in catalog:
                raise RuntimeError(f"duplicate physics formula {spec.id}")
            catalog[spec.id] = spec
    return catalog


CATALOG: dict[str, FormulaSpec] = _register(
    KINEMATICS,
    PROJECTILE,
    SUVAT,
    FORCE,
    ENERGY,
    MOMENTUM,
    FRICTION,
    CIRCULAR,
    SPRING,
    TORQUE,
    ROTATION,
    CIRCUIT,
    WAVES,
    OPTICS,
    THERMAL,
    GRAVITATION,
    FLUIDS,
    MAGNETISM,
    MATERIALS,
    MODERN,
)


def formula_spec(operation: str) -> FormulaSpec | None:
    return CATALOG.get(operation)
