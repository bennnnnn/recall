"""Structured chemistry I/O validated before a deterministic solve.

Extractors do not calculate, and solvers do not guess what the user asked for.
"""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.schemas.chemistry.ops import OPS_BY_KIND, ChemistryKind, ChemistryOp

CrystalGeometry = Literal["octahedral", "tetrahedral", "square_planar"]

# No supported calculation needs more. RDKit and SymPy never see a longer string.
MAX_TEXT_FIELD = 500
MAX_SPECIES = 20
MAX_SAMPLES = 50
MAX_PARAMS = 40
# A typed number is short; anything longer was not read from a question.
MAX_WRITTEN = 32
MAX_DECIMALS = 6
# ``written`` only ever holds a number as typed ("1.10", "-0.76", "1.8e-5"), never other text.
_NUMBER_LITERAL = re.compile(r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?")

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
    # How the question wrote its numbers (chemistry.sig_figs): the answer's significant
    # figures, the decimal places of a logarithm or of a sum of the givens, and each given's
    # text as typed, keyed by repr.
    figures: int | None = Field(default=None, ge=1, le=6)
    decimals: int | None = Field(default=None, ge=0, le=MAX_DECIMALS)
    written: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def finite_values(self) -> ChemistryIntent:
        if self.chemistry_op not in OPS_BY_KIND[self.kind]:
            raise ValueError(f"{self.chemistry_op!r} is not a {self.kind!r} chemistry operation")
        if (
            len(self.species) > MAX_SPECIES
            or len(self.samples) > MAX_SAMPLES
            or len(self.params) > MAX_PARAMS
            or len(self.written) > MAX_PARAMS + MAX_SPECIES + MAX_SAMPLES
            or any(len(text) > MAX_WRITTEN for text in self.written.values())
        ):
            raise ValueError("chemistry intent is larger than any supported calculation")
        if not all(_NUMBER_LITERAL.fullmatch(text) for text in self.written.values()):
            raise ValueError("a written chemistry value must be a number as typed")
        values = (*self.params.values(), *self.species.values(), *self.samples)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("chemistry values must be finite")
        return self
