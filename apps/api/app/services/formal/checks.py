"""The relations a question's own values must keep, tested on those values.

A question can state values that cannot all hold: "a lever balances a load of 1200 N with
an effort of 80 N, 2 m from the load and 3 m from the effort" (live, 2026-11-18) has
1200 N at 2 m (2400 N·m) on one side and 80 N at 3 m (240 N·m) on the other, and its MA
of 15 over a VR of 1.5 is an efficiency of 1000%. A reply that works each part from the
numbers gives four right sums and never says the question is broken.

The model that writes the setup also writes the relations the question's words or a law
require of its values (``FormalProblem.checks``): a stated balance, an equilibrium, a bound
(an efficiency at most 100%). The server tests each on the givens and its own solution,
here, with no word list: a relation broken by more than ``SLACK`` is reported with its two
sides, in the units the setup writes them in.
"""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, Any

from app.services.formal.answer import FormalValue, StatedConflict, card_maths_of
from app.services.formal.problem import Check

if TYPE_CHECKING:
    from app.services.formal.solve import Setup

logger = logging.getLogger(__name__)

# Rounding in the question's own numbers (a load "of about 1200 N") is no contradiction.
SLACK = 0.02
_RELATION = re.compile(r"<=|>=|==|=|<|>")
# The relation the two sides stand in when the check is broken.
_BROKEN = {"=": "\\neq", "==": "\\neq", "<=": ">", "<": ">", ">=": "<", ">": "<"}
_MEANING_MARKS = re.compile(r"[*_`#<>\[\]|$\\]")


def broken_checks(
    checks: list[Check],
    setup: Setup,
    solutions: list[dict[Any, Any]],
    answers: list[FormalValue],
) -> list[StatedConflict]:
    """Each check the values break, in the order the setup wrote them."""
    values = _one_solution(setup, solutions, answers)
    if values is None:
        return []
    broken: list[StatedConflict] = []
    for check in checks:
        try:
            conflict = _broken(check, setup, values)
        except Exception as exc:  # a check that does not read is no check
            logger.info("formal check not read (%s)", type(exc).__name__)
            continue
        if conflict is not None:
            broken.append(conflict)
    return broken


def _one_solution(
    setup: Setup, solutions: list[dict[Any, Any]], answers: list[FormalValue]
) -> dict[Any, float] | None:
    """The givens and the solution the answers were taken from: the only one, or the one
    holding the first answer's value. None when no one solution is that."""
    real = []
    for solution in solutions:
        try:
            real.append({s: float(v.evalf()) for s, v in solution.items()})
        except (TypeError, ValueError):
            continue
    if len(real) > 1 and answers:
        from app.services.formal.solve import in_unit

        first = setup.symbols[answers[0].symbol]
        real = [
            numbers
            for numbers in real
            if first in numbers
            and math.isclose(
                in_unit([numbers[first]], answers[0].unit)[0], answers[0].value, rel_tol=1e-6
            )
        ]
    if len(real) > 1 or (not real and solutions):
        return None
    return setup.values | (real[0] if real else {})


def _broken(check: Check, setup: Setup, values: dict[Any, float]) -> StatedConflict | None:
    from app.services.formal.solve import sympy_tree
    from app.services.law_binding.expression import parse

    relations = _RELATION.findall(check.relation)
    if len(relations) != 1:
        return None
    left_text, right_text = (side.strip() for side in _RELATION.split(check.relation))
    known = dict(setup.symbols)
    sides = [sympy_tree(parse(text.replace("^", "**")), known) for text in (left_text, right_text)]
    if len(known) != len(setup.symbols):
        return None  # a symbol the setup never declared
    left, right = (float(side.subs(values).evalf()) for side in sides)
    relation = relations[0]
    if not _breaks(left, right, relation):
        return None
    return StatedConflict(
        meaning=_meaning(check.meaning),
        left=_side(sides[0], left_text, left, setup),
        broken=_BROKEN[relation],
        right=_side(sides[1], right_text, right, setup),
    )


def _breaks(left: float, right: float, relation: str) -> bool:
    size = max(abs(left), abs(right))
    if size == 0:
        return False
    gap = (left - right) / size
    if relation in {"=", "=="}:
        return abs(gap) > SLACK
    if relation in {"<=", "<"}:
        return gap > SLACK
    return -gap > SLACK


def _side(expression: Any, text: str, value: float, setup: Setup) -> str:
    """A side's value as card maths, in the units its symbols are written in: a moment of
    1200 N at 2 m is 2400 N·m, not 2400 kg·m²/s²."""
    from app.services.formal.solve import kind_of

    try:
        kind = kind_of(expression, setup.written_units)
        base = kind.to_base_units()
        shown = value / float(base.magnitude) if base.magnitude else value
        unit = "" if kind.dimensionless else _in_order(kind.units, text, setup)
    except Exception as exc:  # pint: no unit for it; the number alone
        logger.info("formal check side in base units (%s)", type(exc).__name__)
        shown, unit = value, ""
    return card_maths_of(shown, unit)


def _in_order(units: Any, text: str, setup: Setup) -> str:
    """``units`` with its factors in the order the side names their symbols: a moment
    ``L*d`` is N·m, where pint's own order (by name) wrote m·N."""
    from app.services.formal.solve import unit_registry

    first: dict[str, int] = {}
    for at, name in enumerate(re.findall(r"[A-Za-z_]\w*", text)):
        symbol = setup.symbols.get(name)
        unit = setup.written_units.get(symbol) if symbol is not None else None
        for unit_name in getattr(unit, "_units", {}):
            first.setdefault(unit_name, at)
    items = sorted(units._units.items(), key=lambda item: first.get(item[0], len(first)))
    up = [_power(unit_registry().get_symbol(name), power) for name, power in items if power > 0]
    down = [_power(unit_registry().get_symbol(name), -power) for name, power in items if power < 0]
    if not down:
        return "*".join(up)
    under = down[0] if len(down) == 1 else f"({'*'.join(down)})"
    return f"{'*'.join(up) or '1'}/{under}"


def _power(symbol: str, power: float) -> str:
    return symbol if power == 1 else f"{symbol}**{power:g}"


def _meaning(words: str) -> str:
    """The model's few words, as plain text: no markup, no maths, no trailing stop."""
    return " ".join(_MEANING_MARKS.sub("", words).split()).rstrip(" .;:")
