# ruff: noqa: RUF002, RUF003 -- docstrings and comments show the multiplication sign the reader sees.
"""A given's row on a physics reply: the value as written and, when the working uses it
in SI, the step to that value.

Every row is a true equation: ``3 µC = 3 × 10⁻⁶ C``, ``30 cm = 30 × 0.01 m = 0.3 m``,
``72 km/h = 72 × 1000/3600 m/s = 20 m/s``. Until November 2026 the factor followed the
written unit (``3 µC × 10⁻⁶ = 3 × 10⁻⁶ C``), which read literally is 3 × 10⁻¹² C
(review 2026-11-12, D1). A conversion the substitution never uses is not shown: a
half-life worked in grams and days has no row in kilograms and seconds (D2).
"""

from __future__ import annotations

import math
import re

from app.modules.physics.display import latex_factor, latex_given, latex_unit, si_symbol
from app.modules.physics.solvers.si import PARAM_SI_DIMENSIONS, si_factor, to_si
from app.services.solving import SolveServiceError

# A number in a LaTeX row, in either notation: 0.05, 3 \times 10^{-6}.
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:\s*\\times\s*10\^\{(?P<power>-?\d+)\})?")
# A power or a subscript is the law's, never a given: 2^{4}, (0.2)^{2}, T_{1}.
_POWER = re.compile(r"[_^]\{[^{}]*\}|[_^]\w")
# How close a substituted number is to a given: solvers print four to six figures.
_SAME = 5e-4


def _numbers(arithmetic: str) -> list[float]:
    """Every number the arithmetic writes, outside its powers and subscripts."""
    scripts = [match.span() for match in _POWER.finditer(arithmetic)]
    found: list[float] = []
    for match in _NUMBER.finditer(arithmetic):
        if any(start <= match.start() < end for start, end in scripts):
            continue
        value = float(match.group(0).split(r"\times")[0].strip())
        if match.group("power"):
            value *= 10.0 ** int(match.group("power"))
        found.append(value)
    return found


def _written_in(value: float, numbers: list[float]) -> bool:
    return any(math.isclose(value, number, rel_tol=_SAME) for number in numbers)


def _uses_written(value: float, si_value: float, arithmetic: str) -> bool:
    """Whether the arithmetic works in the written value, not the SI one: 80 in
    ``N = \\frac{80}{2^{4}}`` for 80 g. When it writes neither, the SI step stays."""
    numbers = _numbers(arithmetic)
    return _written_in(value, numbers) and not _written_in(si_value, numbers)


def given_value(name: str, value: float, unit: str, arithmetic: str) -> str:
    """The value as written and, when that is not SI and the arithmetic uses SI, the
    value the solver used, reached by its factor (module docstring). A solver that works
    in the written units (150 km in 2 h) needs no step, and neither do angles or rpm,
    whose formula converts.
    """
    written = f"{latex_given(value)}{latex_unit(unit)}"
    dimension = PARAM_SI_DIMENSIONS.get(name)
    if (
        not unit
        or dimension in (None, "dimensionless", "revolution / minute")
        or name.startswith("angle")
        # Written into the arithmetic as typed: "4 µF", not the "4 µF" ending "2.4 µF".
        or re.search(rf"(?<![\d.]){re.escape(written)}", arithmetic) is not None
    ):
        return written
    try:
        si_value = to_si(value, unit, expected_key=name)
    except SolveServiceError:
        return written
    si_unit = latex_unit(si_symbol(dimension))
    if si_unit == latex_unit(unit) and math.isclose(si_value, value):
        return written
    if _uses_written(value, si_value, arithmetic):
        return written
    reached = f"{latex_given(si_value)}{si_unit}"
    # The factor that makes the SI value: 72 × 1000/3600 m/s. A unit that is SI under
    # another name (N/m² is Pa) has none to show, and a prefix's power of ten needs no
    # step of its own when it is the SI value already (3 × 10⁻⁶ C).
    factor = si_factor(unit, expected_key=name) if value else None
    if factor is not None and not math.isclose(factor[0], factor[1]):
        step = f"{latex_given(value)} {latex_factor(*factor)}{si_unit}"
        if step != reached:
            return f"{written} = {step} = {reached}"
    return f"{written} = {reached}"
