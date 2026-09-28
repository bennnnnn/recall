"""Solvers for the closed school templates.

Returns None for every operation this module does not own, so the existing
kind solvers stay the path for mechanics and the older formulas.
"""

from __future__ import annotations

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import PhysicsResult, _params_in_si
from app.modules.physics.solvers.school_ac import AC_SOLVERS
from app.modules.physics.solvers.school_circuits import CIRCUIT_SOLVERS
from app.modules.physics.solvers.school_fields import FIELD_SOLVERS
from app.modules.physics.solvers.school_matter import MATTER_SOLVERS

_SOLVERS = {
    **CIRCUIT_SOLVERS,
    **FIELD_SOLVERS,
    **AC_SOLVERS,
    **MATTER_SOLVERS,
}


def solve_school_extension(intent: PhysicsIntent) -> PhysicsResult | None:
    op = intent.physics_op or ""
    solver = _SOLVERS.get(op)
    if solver is None:
        return None
    return solver(_params_in_si(intent))
