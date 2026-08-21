"""School homework ops that are not 2D geometry or single-variable calc I."""

from __future__ import annotations

import math

from pint import UnitRegistry
from sympy import (
    Function,
    Symbol,
    cos,
    dsolve,
    factorial,
    latex,
    nsimplify,
    pi,
    simplify,
    sin,
    tan,
)

from app.models.math_schemas import MathExprResult
from app.services.math_service import MathServiceError, _parse_expression

# Pint unit registry (singleton — 50-80ms init, paid once at first use).
# Replaces the hardcoded _LENGTH_TO_M / _MASS_TO_KG / _TIME_TO_S dicts with
# proper dimensional analysis, compound units (m/s², N, J, Pa), and offset
# temperature handling (C/F/K).
_unit_registry: UnitRegistry | None = None


def _get_unit_registry() -> UnitRegistry:
    global _unit_registry
    if _unit_registry is None:
        _unit_registry = UnitRegistry()
    return _unit_registry


# Aliases the old hardcoded tables accepted that Pint doesn't by default.
# Maps user-facing unit strings → Pint-compatible strings.
_UNIT_ALIASES = {
    "in": "inch",
    "inches": "inch",
    "ft": "foot",
    "feet": "foot",
    "foot": "foot",
    "yd": "yard",
    "mi": "mile",
    "miles": "mile",
    "mile": "mile",
    "lbs": "pound",
    "lb": "pound",
    "oz": "ounce",
    "sec": "second",
    "secs": "second",
    "s": "second",
    "mins": "minute",
    "min": "minute",
    "hr": "hour",
    "hrs": "hour",
    "h": "hour",
    "ms": "millisecond",
    "c": "degC",
    "celsius": "degC",
    "f": "degF",
    "fahrenheit": "degF",
    "k": "kelvin",
    "kelvin": "kelvin",
}


def evaluate_arithmetic(expr: str) -> str:
    parsed = _parse_expression(expr, ["x"])
    if isinstance(parsed, tuple):
        raise MathServiceError("not a numeric arithmetic expression")
    if parsed.free_symbols:
        raise MathServiceError("arithmetic expression still has variables")
    value = simplify(parsed)
    return str(latex(value))


def percent_of(rate: float, base: float) -> str:
    value = (rate / 100.0) * base
    return f"{value:g}"


def simplify_ratio(a: int, b: int) -> str:
    from math import gcd

    g = gcd(a, b)
    return f"{a // g}:{b // g}"


def evaluate_trig_degrees(func: str, degrees: float) -> str:
    table = {"sin": sin, "cos": cos, "tan": tan}
    if func not in table:
        raise MathServiceError(f"unsupported trig function {func}")
    exact = simplify(table[func](nsimplify(degrees) * pi / 180))
    return str(latex(exact))


def coord_distance(x1: float, y1: float, x2: float, y2: float) -> str:
    d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return f"{d:g}"


def coord_midpoint(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"({(x1 + x2) / 2:g}, {(y1 + y2) / 2:g})"


def coord_slope(x1: float, y1: float, x2: float, y2: float) -> str:
    if x2 == x1:
        return r"\text{undefined}"
    return f"{(y2 - y1) / (x2 - x1):g}"


def vector_magnitude(vec: list[float]) -> str:
    mag = math.sqrt(sum(c * c for c in vec))
    return f"{mag:g}"


def vector_dot(a: list[float], b: list[float]) -> str:
    if len(a) != len(b):
        raise MathServiceError("dot product needs matching dimension")
    return f"{sum(x * y for x, y in zip(a, b, strict=True)):g}"


def vector_cross(a: list[float], b: list[float]) -> str:
    if len(a) == 2:
        a = [a[0], a[1], 0.0]
        b = [b[0], b[1], 0.0]
    if len(a) != 3 or len(b) != 3:
        raise MathServiceError("cross product needs 2D or 3D vectors")
    cx = a[1] * b[2] - a[2] * b[1]
    cy = a[2] * b[0] - a[0] * b[2]
    cz = a[0] * b[1] - a[1] * b[0]
    return f"({cx:g}, {cy:g}, {cz:g})"


def binomial_pmf(n: int, k: int, p: float) -> str:
    if not (0 <= k <= n) or not (0.0 <= p <= 1.0):
        raise MathServiceError("invalid binomial parameters")
    coeff = int(factorial(n) / (factorial(k) * factorial(n - k)))
    value = coeff * (p**k) * ((1.0 - p) ** (n - k))
    return f"{value:g}"


def expected_value(values: list[float], probs: list[float] | None) -> str:
    if not values:
        raise MathServiceError("expected value needs data")
    if probs is None:
        return f"{sum(values) / len(values):g}"
    if len(probs) != len(values):
        raise MathServiceError("values and probabilities must match")
    return f"{sum(v * p for v, p in zip(values, probs, strict=True)):g}"


def _imaginary_unit_to_sympy(expr: str) -> str:
    """Map standalone ``i``/``j`` to SymPy ``I`` without rewriting ``sin``/``pi``.

    A naive ``str.replace("i", "I")`` turns ``sin`` into ``sIn`` and ``pi``
    into ``pI``. Only replace when the letter is not inside an identifier.
    """
    out: list[str] = []
    n = len(expr)
    for idx, ch in enumerate(expr):
        if ch in ("i", "j"):
            prev_letter = idx > 0 and expr[idx - 1].isalpha()
            next_letter = idx + 1 < n and expr[idx + 1].isalpha()
            if not prev_letter and not next_letter:
                out.append("I")
                continue
        out.append(ch)
    return "".join(out)


def evaluate_complex(expr: str) -> str:
    parsed = _parse_expression(_imaginary_unit_to_sympy(expr), ["x"])
    return str(latex(simplify(parsed)))


def convert_unit(value: float, src: str, dest: str) -> str:
    """Convert a value from one unit to another using Pint dimensional analysis.

    Handles length, mass, time, temperature (C/F/K), and compound units
    (m/s, m/s², N, J, Pa, W, Hz, etc.). Raises MathServiceError on
    unsupported conversions or dimensionality mismatches.
    """
    ureg = _get_unit_registry()

    def _normalize(unit: str) -> str:
        key = unit.lower().strip()
        # Check the alias dict with the full string first (handles "inches",
        # "feet", "celsius", "fahrenheit", "m/s2", etc.), then try the
        # plural-stripped form (handles "meters" → "meter", "seconds" → "second").
        # Only strip plurals from simple word units (no "/" or "^") so compound
        # units like "m/s" aren't broken into "m/", and only from 2+ char words
        # so "s" (second) and "m" (meter) aren't reduced to "".
        if key in _UNIT_ALIASES:
            return _UNIT_ALIASES[key]
        if "/" in key or "^" in key:
            return key  # compound unit — pass through to Pint as-is
        stripped = key.rstrip("s") if len(key) > 1 else key
        if stripped in _UNIT_ALIASES:
            return _UNIT_ALIASES[stripped]
        return stripped

    try:
        src_unit = _normalize(src)
        dest_unit = _normalize(dest)
        # Pint offset units (degC, degF) can't be multiplied by a scalar
        # directly — use Quantity() which handles the offset correctly.
        try:
            quantity = value * ureg(src_unit)
        except Exception:
            quantity = ureg.Quantity(value, src_unit)
        result = quantity.to(dest_unit)
        # Use :.10g for enough precision that test tolerances pass (the old
        # hardcoded dicts used :g which only gave 6 significant digits).
        return f"{float(result.magnitude):.10g}"
    except Exception as exc:
        raise MathServiceError(f"unsupported conversion {src} to {dest}") from exc


def taylor_series(expr: str, variable: str, point: str, order: int) -> MathExprResult:
    from sympy import series

    parsed = _parse_expression(expr, [variable])
    var = Symbol(variable)
    pt = _parse_expression(point, [variable])
    out = series(parsed, var, pt, order + 1).removeO()
    tex = str(latex(out))
    return MathExprResult(result=tex, latex=tex, solved=True)


def partial_derivative(expr: str, variable: str) -> MathExprResult:
    from sympy import diff

    parsed = _parse_expression(expr, [variable])
    out = diff(parsed, Symbol(variable))
    tex = str(latex(out))
    return MathExprResult(result=tex, latex=tex, solved=True)


def solve_ode(expr: str, variable: str = "x") -> MathExprResult:
    """First-order ODE: ``dy/dx = ...`` or ``y' = ...`` in ``expr`` as Eq."""
    y = Function("y")
    ivar = Symbol(variable)
    text = expr.replace("y'", f"Derivative(y({variable}), {variable})")
    text = text.replace("dy/dx", f"Derivative(y({variable}), {variable})")
    parsed = _parse_expression(text, [variable])
    try:
        sol = dsolve(parsed, y(ivar))
    except Exception as exc:
        raise MathServiceError("could not solve ODE") from exc
    tex = str(latex(sol))
    return MathExprResult(result=tex, latex=tex, solved=True)


def evaluate_trig_expr(expr: str) -> str:
    parsed = _parse_expression(expr.replace("\u00b0", "*pi/180"), ["x"])
    return str(latex(simplify(parsed)))
