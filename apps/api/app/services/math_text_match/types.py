"""Linear (non-regex / digit-only-regex) matchers for math intent heuristics."""

from __future__ import annotations

from typing import Literal

StatsOp = Literal["mean", "median", "mode", "variance", "stdev"]
CombinatoricsOp = Literal["factorial", "combinations", "permutations"]
NumberTheoryOp = Literal["gcd", "lcm", "factorize", "is_prime", "mod"]
MatrixOp = Literal["determinant", "inverse"]
SolidShape = Literal["cube", "rectangular_prism", "cylinder", "cone", "sphere", "pyramid"]
