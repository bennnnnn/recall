"""Structured chemistry I/O validated before a deterministic solve.

Extractors do not calculate, and solvers do not guess what the user asked for.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, model_validator

from app.models.schemas.chemistry.ops import _OPS_BY_KIND, ChemistryKind, ChemistryOp

__all__ = ["ChemistryIntent", "ChemistryKind", "ChemistryOp"]


class ChemistryIntent(BaseModel):
    """One unambiguous chemistry calculation.

    ``params`` contains canonical numeric variables and ``units`` records how
    they were supplied for user-visible Given lines. Textual chemistry data
    (formula, equation, target species) is explicit rather than hidden inside
    a generic params dictionary.
    """

    kind: ChemistryKind
    chemistry_op: ChemistryOp
    params: dict[str, float] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    formula: str | None = None
    equation: str | None = None
    target: str | None = None
    species: dict[str, float] = Field(default_factory=dict)
    samples: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def finite_values(self) -> ChemistryIntent:
        if self.chemistry_op not in _OPS_BY_KIND[self.kind]:
            raise ValueError(f"{self.chemistry_op!r} is not a {self.kind!r} chemistry operation")
        values = (*self.params.values(), *self.species.values(), *self.samples)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("chemistry values must be finite")
        return self
