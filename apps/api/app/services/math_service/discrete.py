"""Statistics, combinatorics, number theory, matrices."""

from __future__ import annotations

import math
import re
import statistics as _stats

from sympy import latex

from app.models.math_schemas import (
    CombinatoricsInput,
    CombinatoricsResult,
    MatrixInput,
    MatrixResult,
    NumberTheoryInput,
    NumberTheoryResult,
    StatisticsInput,
    StatisticsResult,
)
from app.services.math_service.parse import MathServiceError

_FUNCTION_NAME_RE = re.compile(
    r"\b(?:sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|sqrt|exp|min|max|abs)\b",
    re.IGNORECASE,
)

# Multi-letter mathematical constants that must NOT be split into per-letter
# variable candidates. Without this, "sin(pi*x) = 0" would guess 'i' and 'p'
# as variables (alphabetically before 'x'), silently solving for the wrong
# symbol. SymPy recognizes these as constants, so the guesser must too.
_CONSTANT_NAMES_RE = re.compile(
    r"\b(?:pi|oo|inf|infinity|nan)\b",
    re.IGNORECASE,
)


def guess_variables(text: str) -> list[str]:
    """BUG FIX: a bare per-letter scan treated function-name letters as
    candidate variables -- "cos(x) = 0" guessed 'c' (alphabetically first of
    c/o/s/x) instead of 'x', silently solving for the wrong symbol. Strip
    recognized function names AND multi-letter constants (pi, oo, ...) before
    extracting letters, so "sin(pi*x) = 0" guesses 'x' not 'i'/'p'."""
    stripped = _FUNCTION_NAME_RE.sub(" ", text)
    stripped = _CONSTANT_NAMES_RE.sub(" ", stripped)
    found = sorted(set(re.findall(r"[a-zA-Z]", stripped)))
    # Exclude single-letter constants: e (Euler's number), i (imaginary unit
    # in some contexts, though commonly a variable index -- keep it for now
    # since 'i' is far more often a loop variable than the imaginary unit in
    # user input). E (uppercase) is SymPy's Euler number.
    letters = [c for c in found if c not in {"e", "E"}]
    return letters[:4] if letters else ["x"]


def compute_statistics(data: StatisticsInput) -> StatisticsResult:
    """Mean/median/mode/variance/stdev for a raw list of numbers — stdlib
    `statistics`, not SymPy (no expression parsing needed for plain floats)."""
    numbers = data.numbers
    n = len(numbers)
    total = math.fsum(numbers)
    mean_val = total / n
    median_val = _stats.median(numbers)
    # multimode() returns every value tied for most frequent — when every
    # value is unique that's the WHOLE list, which isn't a meaningful mode.
    modes = sorted(_stats.multimode(numbers))
    if len(modes) == n and n > 1:
        modes = []
    variance_population = _stats.pvariance(numbers)
    stdev_population = _stats.pstdev(numbers)
    variance_sample = _stats.variance(numbers) if n >= 2 else None
    stdev_sample = _stats.stdev(numbers) if n >= 2 else None
    range_val = max(numbers) - min(numbers)
    labels = {
        "count": str(n),
        "sum": f"{total:g}",
        "mean": f"{mean_val:g}",
        "median": f"{median_val:g}",
        "mode": ", ".join(f"{m:g}" for m in modes) if modes else "none",
        "range": f"{range_val:g}",
        "population_stdev": f"{stdev_population:.4f}",
        "sample_stdev": f"{stdev_sample:.4f}" if stdev_sample is not None else "n/a",
    }
    return StatisticsResult(
        count=n,
        numbers=numbers,
        sum=round(total, 6),
        mean=round(mean_val, 6),
        median=round(median_val, 6),
        modes=modes,
        range=round(range_val, 6),
        variance_population=round(variance_population, 6),
        stdev_population=round(stdev_population, 6),
        variance_sample=round(variance_sample, 6) if variance_sample is not None else None,
        stdev_sample=round(stdev_sample, 6) if stdev_sample is not None else None,
        labels=labels,
    )


def compute_combinatorics(data: CombinatoricsInput) -> CombinatoricsResult:
    """Factorial / nCr / nPr — plain integer arithmetic (math.factorial/comb/
    perm), not SymPy: these never touch the untrusted-expression parser."""
    if data.operation == "factorial":
        if data.n > 170:
            raise MathServiceError("Factorial input is capped at 170")
        result = math.factorial(data.n)
        return CombinatoricsResult(
            operation="factorial",
            n=data.n,
            k=None,
            result=result,
            steps=[f"{data.n}! = {result}"],
        )
    if data.k is None or data.k < 0 or data.k > data.n:
        raise MathServiceError("k must satisfy 0 <= k <= n")
    if data.operation == "combinations":
        result = math.comb(data.n, data.k)
        steps = [
            f"C({data.n},{data.k}) = {data.n}! / ({data.k}! \\times "
            f"({data.n}-{data.k})!) = {result}"
        ]
    else:
        result = math.perm(data.n, data.k)
        steps = [f"P({data.n},{data.k}) = {data.n}! / ({data.n}-{data.k})! = {result}"]
    return CombinatoricsResult(
        operation=data.operation, n=data.n, k=data.k, result=result, steps=steps
    )


def compute_number_theory(data: NumberTheoryInput) -> NumberTheoryResult:
    """GCD / LCM / prime factorization / primality / modulo — integer-only,
    bypasses the expression parser entirely (see NumberTheoryInput's bounds
    for why factorize/is_prime stay fast even on an adversarial input)."""
    a = data.a
    if data.operation in ("gcd", "lcm", "mod"):
        if data.b is None:
            raise MathServiceError(f"{data.operation} requires two integers")
        b = data.b
        if data.operation == "gcd":
            result = math.gcd(a, b)
            steps = [f"gcd({a}, {b}) = {result}"]
        elif data.operation == "lcm":
            result = math.lcm(a, b)
            steps = [f"lcm({a}, {b}) = {result}"]
        else:
            if b == 0:
                raise MathServiceError("Modulo by zero is undefined")
            result = a % b
            steps = [f"{a} \\bmod {b} = {result}"]
        return NumberTheoryResult(
            operation=data.operation, a=a, b=b, result_int=result, steps=steps
        )

    if data.operation == "factorize":
        from sympy import factorint

        if a < 2:
            raise MathServiceError("Prime factorization needs an integer >= 2")
        raw_factors = factorint(a)
        factors = {int(p): int(e) for p, e in raw_factors.items()}
        parts = [(f"{p}^{{{e}}}" if e > 1 else f"{p}") for p, e in sorted(factors.items())]
        steps = [f"{a} = " + " \\times ".join(parts)]
        return NumberTheoryResult(operation="factorize", a=a, b=None, factors=factors, steps=steps)

    # is_prime
    from sympy import isprime

    result_bool = bool(isprime(a))
    steps = [f"{a} is {'prime' if result_bool else 'not prime'}"]
    return NumberTheoryResult(
        operation="is_prime", a=a, b=None, result_bool=result_bool, steps=steps
    )


def compute_matrix(data: MatrixInput) -> MatrixResult:
    """Determinant / inverse of a small square matrix via sympy.Matrix.
    Entries are plain floats from Pydantic (never sympified from raw text),
    so this never touches the untrusted-expression parser either. Converted
    via Rational(str(v)) rather than left as float — sympy.Matrix keeps
    float entries as floats, so e.g. an inverse's 1/6 entry would otherwise
    print as the illegible "0.166666666666667" instead of a clean fraction.
    """
    from sympy import Matrix, Rational

    mat = Matrix([[Rational(str(v)) for v in row] for row in data.rows])
    if mat.rows != mat.cols:
        raise MathServiceError("determinant/inverse need a square matrix")
    det = mat.det()
    if data.operation == "determinant":
        steps = [f"\\det = {latex(det)}"]
        return MatrixResult(operation="determinant", determinant=float(det), steps=steps)

    if det == 0:
        raise MathServiceError("Matrix is singular (determinant is 0) — no inverse exists")
    inv = mat.inv()
    steps = [f"\\det = {latex(det)}", f"\\text{{inverse}} = {latex(inv)}"]
    return MatrixResult(
        operation="inverse", determinant=float(det), inverse_latex=latex(inv), steps=steps
    )
