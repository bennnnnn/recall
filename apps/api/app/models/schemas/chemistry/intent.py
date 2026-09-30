"""Structured chemistry I/O validated before a deterministic solve.

Extractors do not calculate, and solvers do not guess what the user asked for.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.schemas.chemistry.ops import _OPS_BY_KIND, ChemistryKind, ChemistryOp

CrystalGeometry = Literal["octahedral", "tetrahedral", "square_planar"]

# No supported calculation needs more. RDKit and SymPy never see a longer string.
MAX_TEXT_FIELD = 500
MAX_SPECIES = 20
MAX_SAMPLES = 50
MAX_PARAMS = 40

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
    formula: str | None = Field(default=None, max_length=MAX_TEXT_FIELD)
    equation: str | None = Field(default=None, max_length=MAX_TEXT_FIELD)
    target: str | None = Field(default=None, max_length=MAX_TEXT_FIELD)
    geometry: CrystalGeometry | None = None
    species: dict[str, float] = Field(default_factory=dict)
    samples: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def finite_values(self) -> ChemistryIntent:
        if self.chemistry_op not in _OPS_BY_KIND[self.kind]:
            raise ValueError(f"{self.chemistry_op!r} is not a {self.kind!r} chemistry operation")
        if (
            len(self.species) > MAX_SPECIES
            or len(self.samples) > MAX_SAMPLES
            or len(self.params) > MAX_PARAMS
        ):
            raise ValueError("chemistry intent is larger than any supported calculation")
        values = (*self.params.values(), *self.species.values(), *self.samples)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("chemistry values must be finite")
        return self
