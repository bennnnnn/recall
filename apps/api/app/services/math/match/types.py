"""Linear (non-regex / digit-only-regex) matchers for math intent heuristics."""

from __future__ import annotations

from typing import Literal

StatsOp = Literal[
    "mean",
    "median",
    "mode",
    "variance",
    "stdev",
    "sample_stdev",
    "sample_variance",
    "range",
    "iqr",
    "quartiles",
    "percentile",
]
CombinatoricsOp = Literal["factorial", "combinations", "permutations"]
NumberTheoryOp = Literal[
    "gcd", "lcm", "factorize", "is_prime", "mod", "mod_inverse", "totient", "crt"
]
MatrixOp = Literal["determinant", "inverse", "multiply", "rref", "eigenvalues", "add", "transpose"]
SolidShape = Literal["cube", "rectangular_prism", "cylinder", "cone", "sphere", "pyramid"]
