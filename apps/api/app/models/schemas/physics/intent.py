"""Structured physics I/O — validated before SymPy and fence emission.

Split out of ``MathIntent`` (see docs/SUBJECT_SEPARATION_TICKETS.md, S1): physics's real
footprint on the old shared model was narrow — ``kind`` (twenty of its forty-nine values),
``operation`` (always ``"solve"``), and the three ``physics_*`` fields. Everything else on
``MathIntent`` (``lhs``/``rhs``, ``school_op``, geometry dimensions, ...) is genuinely
math's, not physics's, and stays there.

``PhysicsIntent`` flows only through the physics-owned extractor, block builder, solver,
and presentation boundary. The subject-neutral chat dispatcher may carry either a math
or physics result, but neither subject imports or registers the other's algorithms.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ProjectileQuantity = Literal["time_of_flight", "max_height", "range", "impact_speed"]


class PhysicsIntent(BaseModel):
    kind: Literal[
        "kinematics",
        "projectile",
        "force",
        "energy",
        "momentum",
        "friction",
        "circular",
        "spring",
        "circuit",
        "torque",
        "suvat",
        "waves",
        "optics",
        "thermal",
        "gravitation",
        "fluids",
        "rotation",
        "magnetism",
        "materials",
        "modern",
    ]
    # Physics never sets anything but "solve" — narrower than MathIntent.operation
    # on purpose, but the same field name so generic dispatch code that reads
    # `.operation` on "whichever intent an extractor returned" (e.g.
    # `direct_calculus.py`'s `actual.operation == "dsolve"`) never needs to know
    # or care which of the two types it was handed.
    operation: Literal["solve"] = "solve"
    # A catalog id. The catalog is the one list of operations: the validator
    # below refuses an id it does not declare, so no second list is kept here.
    physics_op: str | None = Field(default=None, max_length=64)
    # Initial conditions / knowns: {"h0": 20.0, "v0": 0.0, "g": 9.81, ...}.
    # Keys are the canonical variable names the solver expects.
    physics_params: dict[str, float] | None = None
    # Unit labels for the params above: {"h0": "m", "v0": "m/s", "g": "m/s^2"}.
    # Used to render the answer with proper units.
    physics_units: dict[str, str] | None = None
    # One launch, with every requested output retained in presentation order.
    requested_ops: list[ProjectileQuantity] = Field(default_factory=list, max_length=4)
    # Dimensions the question asks for, read independently of the extractor.
    # Empty when the ask could not be read; then no result is refused for it.
    asked: tuple[str, ...] = Field(default=(), max_length=4)
    # "in kWh": the unit the answer is shown in, as the question spelled it.
    asked_unit: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def coherent_requested_ops(self) -> PhysicsIntent:
        ops = self.requested_ops
        if ops:
            if self.kind != "projectile" or self.physics_op != ops[0]:
                raise ValueError("multipart quantities must belong to the same projectile")
            if len(ops) < 2 or len(set(ops)) != len(ops):
                raise ValueError("multipart quantities must contain two to four distinct requests")
        self._catalog_owns_operation()
        return self

    def _catalog_owns_operation(self) -> None:
        """Reject a kind, operation, or parameter the formula catalog does not contain.

        The catalog declares each operation and the variables it accepts. The
        catalog does not import this module.
        """
        if self.physics_op is None:
            return
        from app.modules.physics.catalog import CATALOG

        spec = CATALOG.get(self.physics_op)
        if spec is None or spec.kind != self.kind:
            raise ValueError(f"{self.kind} does not define {self.physics_op}")
        allowed = {variable.name for variable in spec.variables}
        params = set(self.physics_params or {})
        unknown = params - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"{self.physics_op} does not declare {names}")
        extra_units = set(self.physics_units or {}) - params
        if extra_units:
            names = ", ".join(sorted(extra_units))
            raise ValueError(f"{self.physics_op} units are not parameters: {names}")
