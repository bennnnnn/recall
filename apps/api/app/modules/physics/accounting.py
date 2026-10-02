"""Numeric accountability: a verified solve may not skip a competing given.

The extractors bind values by keyword nearness. When a question states two
quantities of the kind a formula uses and the solve binds only one, the
keyword chose: "from 20 °C to 80 °C" became ΔT = 20, and "a KE at 3 m/s and
at 4 m/s" answered only the first. Such a solve is declined, not verified.

A quantity of a kind the formula never uses is a distractor and stays
allowed: a ball's mass does not change its fall time. A value the extractor
derived by adding or subtracting givens accounts for them: currents of 2 A
and 3 A entering a junction are the 5 A it binds, and 80 °C and 20 °C are
the 60 K it heats by.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from itertools import combinations, product

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import _NUMBER
from app.modules.physics.givens import ANGLE, Given, scan_givens, unit_dimension
from app.modules.physics.solvers.common import _PARAM_SI_DIMENSIONS, _to_si
from app.services.solving import SolveServiceError

logger = logging.getLogger(__name__)

# A stated g is a setting for whichever law needs it, not a competing given.
_GRAVITY_SETTING = re.compile(
    rf"\b(?:g\s*=|gravity\s*(?:of|is|=)?)\s*{_NUMBER}(?:\s*m/s\^?2)?",
    re.IGNORECASE,
)
# Derived values are sums or differences of a few givens; more is a guess.
_MAX_OPERANDS = 4
_MAX_SAME_KIND = 6


@dataclass(frozen=True, slots=True)
class _Param:
    dimension: str
    raw: float
    si: float | None


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-12)


def _param_dimension(key: str) -> str | None:
    expression = _PARAM_SI_DIMENSIONS.get(key)
    if expression is None:
        return None
    if key.startswith("angle") or expression in {"radian", "degree"}:
        return ANGLE
    reading = unit_dimension(expression)
    return None if reading is None else reading[0]


def _params(intent: PhysicsIntent) -> list[_Param]:
    units = intent.physics_units or {}
    params: list[_Param] = []
    for key, value in (intent.physics_params or {}).items():
        dimension = _param_dimension(key)
        if dimension is None:
            continue
        unit = units.get(key, "")
        si: float | None
        if dimension == ANGLE:
            si = value if unit.lower().startswith("rad") else math.radians(value)
        else:
            try:
                si = _to_si(value, unit, expected_key=key)
            except SolveServiceError:
                si = None
        params.append(_Param(dimension, value, si))
    return params


def _bound(given: Given, params: list[_Param]) -> bool:
    # Magnitudes: extractors carry direction as a sign ("5 m/s downward" is -5).
    return any(
        _same(abs(given.value), abs(param.raw))
        or (given.si is not None and param.si is not None and _same(abs(given.si), abs(param.si)))
        for param in params
    )


def _derived(given: Given, others: list[Given], params: list[_Param]) -> bool:
    """Whether a bound value is a signed sum of this given and a few others."""
    if len(others) > _MAX_SAME_KIND:
        return False
    targets = [abs(param.raw) for param in params]
    si_targets = [abs(param.si) for param in params if param.si is not None]
    for size in range(1, _MAX_OPERANDS):
        for group in combinations(others, size):
            operands = (given, *group)
            for signs in product((1.0, -1.0), repeat=len(group)):
                raw = given.value + sum(s * g.value for s, g in zip(signs, group, strict=True))
                if any(_same(abs(raw), target) for target in targets):
                    return True
                if all(item.si is not None for item in operands):
                    si = (given.si or 0.0) + sum(
                        s * (g.si or 0.0) for s, g in zip(signs, group, strict=True)
                    )
                    if any(_same(abs(si), target) for target in si_targets):
                        return True
    return False


def competing_given(intent: PhysicsIntent, text: str) -> Given | None:
    """A stated quantity of a kind this solve uses that it neither bound nor derived."""
    params = _params(intent)
    settings = [match.span() for match in _GRAVITY_SETTING.finditer(text)]
    givens = [
        given
        for given in scan_givens(text)
        if given.dimension is not None
        and not any(start <= given.start < end for start, end in settings)
    ]
    for given in givens:
        same_kind = [param for param in params if param.dimension == given.dimension]
        if not same_kind or _bound(given, same_kind):
            continue
        others = [
            other for other in givens if other is not given and other.dimension == given.dimension
        ]
        if _derived(given, others, same_kind):
            continue
        logger.info(
            "physics solve declined: %s %s left unbound by op=%s",
            given.value,
            given.unit,
            intent.physics_op,
        )
        return given
    return None
