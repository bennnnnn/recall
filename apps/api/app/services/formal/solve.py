"""Check a model's written-down setup and solve it: the server does the arithmetic.

``solve_formal`` takes a ``FormalProblem`` (as JSON, so it crosses into the SymPy pool) and
the question, and answers with a ``FormalResult``. In order, a setup is refused when:

1. a given's words are not in the question, or its number is not in those words: the
   setup used a value the student never gave;
2. a constant the question does not state is not a standard one (``formal.constants``);
3. an equation does not parse as plain arithmetic in the declared symbols (the tree is
   walked, never executed: ``law_binding.expression.parse``);
4. an equation's two sides are not the same kind of quantity (pint), or a sine's argument
   has a unit: the physics is wrong whatever the numbers;
5. SymPy finds no real solution, or several the setup cannot tell apart;
6. the solution does not satisfy every equation when put back.

Steps 5 and 6 are held to each asked part on its own: a part they refuse is left out and
the others are answered. Each answer is in the unit the question asked for, with the range
the standard constants it uses allow (g as 9.8, 9.81 or 10) and the question's numbers it
is worked from, so a reply can be held to it (``chat.formal_turn``). The setup's checks
the question's own values break are reported too (``formal.checks``). Whether an answer
agrees with the model's own is reported, not decided here: the caller chooses what a
student sees.
"""

from __future__ import annotations

import ast
import json
import keyword
import logging
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.formal.answer import FormalValue, StatedConflict
from app.services.formal.checks import broken_checks
from app.services.formal.constants import TOLERANCE, is_standard, standard_value
from app.services.formal.maths import (
    Setup,
    as_quantity,
    in_unit,
    kind_of,
    sympy_tree,
    unit_registry,
)
from app.services.formal.problem import Asked, FormalProblem

logger = logging.getLogger(__name__)

AGREEMENT = 0.01
_MAX_EQUATION_CHARS = 300
_RESIDUAL = 1e-6
# The factors an equation may write itself: small whole numbers, halves, quarters and thirds.
_PLAIN_NUMBERS = frozenset(
    {float(n) for n in range(13)} | {n / d for d in (2, 3, 4) for n in range(1, 13)}
)
_MAX_SYMBOL = 24
_KEYWORD = re.compile(rf"\b(?:{'|'.join(keyword.kwlist)})\b")
# Names the tree reads as functions or pi: a symbol may not shadow them. Symbols are built
# directly, never parsed from text, so I (a current) or E (a field) are plain symbols.
_RESERVED = frozenset(
    {"pi", "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "exp", "log", "abs"}
)
_NUMBER = re.compile(
    "[-\u2212]?\\d[\\d\\s.,]*(?:\\s*(?:[eE]|[\u00d7x*]\\s*10\\s*\\^?\\*{0,2})\\s*[-\u2212+]?\\d+)?"
)


@dataclass
class FormalResult:
    solved: bool
    reason: str = ""
    # The server's value for each part it could work out, in the order asked.
    answers: list[FormalValue] = field(default_factory=list)
    # The checks the question's own values break.
    conflicts: list[StatedConflict] = field(default_factory=list)


def _refused(reason: str) -> str:
    return json.dumps(asdict(FormalResult(solved=False, reason=reason)))


def parse_number(text: str) -> float | None:
    """A number as a person writes it: "1,200", "2,5" (a decimal comma), "3e8", "3 x 10^8"."""
    raw = unicodedata.normalize("NFKC", text).strip().replace("\u2212", "-").replace(" ", "")
    power = re.fullmatch("(-?[\\d.,]+)(?:[\u00d7x*]10\\^?\\*{0,2}|[eE])([-+]?\\d+)", raw)
    mantissa, exponent = (power.group(1), int(power.group(2))) if power else (raw, 0)
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", mantissa):
        mantissa = mantissa.replace(",", "")
    elif re.fullmatch(r"-?\d+,\d+", mantissa):
        mantissa = mantissa.replace(",", ".")
    try:
        return float(mantissa) * 10.0**exponent
    except ValueError:
        return None


def _folded(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def grounded(value: float, quote: str, question: str, *, count: bool = False) -> bool:
    """The given's words are in the question and say its number. Words with no digits say
    only a state's zero ("from rest", "desde el reposo") or, for a pure number (``count``),
    a whole count up to twelve ("two resistors", "dos resistencias"): a time, a length or a
    speed takes its number from the question's digits, never from any words it holds."""
    if not quote.strip() or _folded(quote) not in _folded(question):
        return False
    numbers = [parse_number(match.group()) for match in _NUMBER.finditer(quote)]
    if any(n is not None and math.isclose(n, value, rel_tol=1e-9) for n in numbers):
        return True
    if numbers:
        return False
    return value == 0 or (count and float(value).is_integer() and 1 <= value <= 12)


def _plain(node: ast.AST) -> bool:
    """A number written into an equation is a plain factor (2 in v**2/2, 4 in 4*pi); a value
    the question gives is a given, held to the question's words."""
    if not isinstance(node, ast.Constant):
        return True
    value = node.value
    if isinstance(value, bool) or not isinstance(value, int | float):
        return True
    return float(value) in _PLAIN_NUMBERS


def _equation(text: str, symbols: dict[str, Any]) -> tuple[Any, Any]:
    from app.services.law_binding.expression import parse

    if len(text) > _MAX_EQUATION_CHARS or text.count("=") != 1:
        raise ValueError("one '=' per equation")
    left, right = (part.strip().replace("^", "**") for part in text.split("="))
    trees = [parse(left), parse(right)]
    if any(isinstance(node, ast.IfExp | ast.Compare) for tree in trees for node in ast.walk(tree)):
        raise ValueError("no conditions")
    if not all(_plain(node) for tree in trees for node in ast.walk(tree)):
        raise ValueError("a value written into an equation, not given")
    return sympy_tree(trees[0], symbols), sympy_tree(trees[1], symbols)


def _dimensions_agree(sides: tuple[Any, Any], units: dict[Any, Any]) -> bool:
    """Both sides are the same kind of quantity; a side that is 0 is any kind."""
    try:
        kinds = [None if side == 0 else kind_of(side, units) for side in sides]
    except Exception as exc:  # pint: kinds that do not add, or a unit inside a function
        logger.info("formal setup: an equation mixes kinds (%s)", type(exc).__name__)
        return False
    left, right = kinds
    return left is None or right is None or bool(left.dimensionality == right.dimensionality)


def _infer_units(equations: list[tuple[Any, Any]], units: dict[Any, Any], extra: set[Any]) -> bool:
    """A symbol the setup uses without declaring (``v_y = v*sin(theta)``) takes the kind of
    what it equals. False when one is left whose kind no equation gives."""
    left_to_find = set(extra)
    progress = True
    while left_to_find and progress:
        progress = False
        for sides in equations:
            for alone, other in (sides, sides[::-1]):
                if alone in left_to_find and not (other.free_symbols & left_to_find):
                    try:
                        units[alone] = kind_of(other, units).to_base_units().units
                    except Exception as exc:  # pint, as above
                        logger.info("formal setup: no kind for a symbol (%s)", type(exc).__name__)
                        return False
                    left_to_find.discard(alone)
                    progress = True
    return not left_to_find


def _target_values(
    solutions: list[dict[Any, Any]], target: Any, unknowns: list[Any]
) -> list[float]:
    """The target's real values over the solutions whose every unknown is real."""
    values: list[float] = []
    for solution in solutions:
        try:
            numbers = {s: complex(solution[s].evalf()) for s in unknowns if s in solution}
        except (TypeError, KeyError):
            continue
        if target not in numbers or any(
            abs(n.imag) > 1e-9 * max(1, abs(n.real)) for n in numbers.values()
        ):
            continue
        value = numbers[target].real
        if math.isfinite(value) and all(not math.isclose(value, v, rel_tol=1e-9) for v in values):
            values.append(value)
    return values


def _clean(text: str) -> str:
    """LaTeX marks a model may write in a name: ``\\theta`` is ``theta``, ``v_{0}`` is ``v_0``;
    a Python keyword used as a name (``lambda`` for a wavelength) is ``lambda_``."""
    text = text.replace("\\", "").replace("{", "").replace("}", "").strip()
    return _KEYWORD.sub(lambda match: f"{match.group()}_", text)


def _cleaned(problem: FormalProblem) -> FormalProblem:
    return problem.model_copy(
        update={
            "givens": [g.model_copy(update={"symbol": _clean(g.symbol)}) for g in problem.givens],
            "unknowns": [
                u.model_copy(update={"symbol": _clean(u.symbol)}) for u in problem.unknowns
            ],
            "equations": [_clean(e) for e in problem.equations],
            "asked": [a.model_copy(update={"symbol": _clean(a.symbol)}) for a in problem.asked],
            "checks": [
                c.model_copy(update={"relation": _clean(c.relation)}) for c in problem.checks
            ],
        }
    )


class _Refused(Exception):
    """The setup does not hold; its message is the reason."""


def _symbols(problem: FormalProblem) -> dict[str, Any]:
    import sympy

    names = [g.symbol for g in problem.givens] + [u.symbol for u in problem.unknowns]
    if len(set(names)) != len(names) or any(
        not n.isidentifier() or len(n) > _MAX_SYMBOL or n in _RESERVED for n in names
    ):
        raise _Refused("symbols")
    return {n: sympy.Symbol(n, real=True) for n in names}


def _given_base(given: Any, registry: Any) -> tuple[float | None, Any]:
    """The number the question writes and the value in base SI; a standard constant named
    with no value takes the table's, when only one is of its kind (water's specific heat)."""
    number = parse_number(given.value)
    if number is None and given.constant:
        kind = as_quantity(1.0, given.unit).to_base_units().units
        number = standard_value(kind, registry)
        return number, None if number is None else registry.Quantity(number, kind)
    return number, None if number is None else as_quantity(number, given.unit).to_base_units()


def _read_givens(problem: FormalProblem, question: str, setup: Setup) -> None:
    registry = unit_registry()
    for given in problem.givens:
        symbol = setup.symbols[given.symbol]
        number, base = _given_base(given, registry)
        if base is None or number is None:
            raise _Refused(f"value of {given.symbol}")
        if given.constant:
            if not is_standard(base.magnitude, base.units, registry):
                raise _Refused(f"constant {given.symbol} is no standard value")
            setup.constants.add(symbol)
        elif not grounded(number, given.quote, question, count=bool(base.dimensionless)):
            raise _Refused(f"{given.symbol} is not in the question")
        setup.values[symbol] = float(base.magnitude)
        setup.written[symbol] = number
        setup.units[symbol] = base.units
        setup.written_units[symbol] = as_quantity(1.0, given.unit).units


def _read_setup(problem: FormalProblem, question: str) -> Setup:
    """Every check of the module docstring's steps 1 to 4, in order."""
    symbols = _symbols(problem)
    setup = Setup(symbols, {}, {}, {}, set(), [], [])
    try:
        _read_givens(problem, question, setup)
        for unknown in problem.unknowns:
            written = as_quantity(1.0, unknown.unit)
            setup.units[symbols[unknown.symbol]] = written.to_base_units().units
            setup.written_units[symbols[unknown.symbol]] = written.units
        for asked in problem.asked:
            target = symbols.get(asked.symbol)
            if target is None or target in setup.values:
                raise _Refused("an asked value is no unknown")
            kind = as_quantity(1.0, asked.unit).to_base_units().dimensionality
            if kind != setup.units[target].dimensionality:
                raise _Refused("asked unit")
    except _Refused:
        raise
    except Exception as exc:  # pint: a unit it cannot read
        logger.info("formal setup: unit not read (%s)", type(exc).__name__)
        raise _Refused(f"unit ({type(exc).__name__})") from exc
    declared = set(symbols.values())
    try:
        setup.equations = [_equation(text, symbols) for text in problem.equations]
    except Exception as exc:  # the tree refused it: not plain arithmetic
        logger.info("formal setup: equation refused (%s)", type(exc).__name__)
        raise _Refused(f"equation: {str(exc)[:60]}") from exc
    extra = set(symbols.values()) - declared
    if not _infer_units(setup.equations, setup.units, extra):
        raise _Refused("a symbol no equation gives the kind of")
    setup.unknowns = [symbols[u.symbol] for u in problem.unknowns] + sorted(extra, key=str)
    setup.written_units |= {symbol: setup.units[symbol] for symbol in extra}
    if not all(_dimensions_agree(sides, setup.units) for sides in setup.equations):
        raise _Refused("units of an equation")
    return setup


def _solutions(setup: Setup, values: dict[Any, float]) -> tuple[list[Any], list[dict[Any, Any]]]:
    import sympy

    system = [sympy.Eq(left.subs(values), right.subs(values)) for left, right in setup.equations]
    try:
        solutions = sympy.solve(system, setup.unknowns, dict=True)
    except Exception as exc:  # SymPy found no closed form
        logger.info("formal setup: not solved (%s)", type(exc).__name__)
        raise _Refused(f"solve ({type(exc).__name__})") from exc
    return system, solutions if isinstance(solutions, list) else []


def _uses(setup: Setup, target: Any) -> set[Any]:
    """The givens ``target`` is worked out from: those in the equations that reach it
    through unknowns. A value the question adds and no equation joins to it is not one."""
    reached: set[Any] = {target}
    used: set[Any] = set()
    grew = True
    while grew:
        grew = False
        for left, right in setup.equations:
            symbols = left.free_symbols | right.free_symbols
            if symbols & reached and not symbols <= reached | used:
                used |= {s for s in symbols if s in setup.values}
                reached |= {s for s in symbols if s not in setup.values}
                grew = True
    return used


def _band(setup: Setup, target: Any, unit: str, value: float, uses: set[Any]) -> list[float]:
    """The asked value with each standard constant it uses at either end of its tolerance:
    g as 9.8 or 10 gives a value just as right as 9.81's (an assumption, not an error)."""
    found = [value]
    for constant in sorted(uses & setup.constants, key=str):
        for factor in (1 - TOLERANCE, 1 + TOLERANCE):
            changed = setup.values | {constant: setup.values[constant] * factor}
            try:
                _system, solutions = _solutions(setup, changed)
            except _Refused:
                continue
            candidates = _target_values(solutions, target, setup.unknowns)
            shown = in_unit(candidates, unit)
            if shown:
                found.append(min(shown, key=lambda v: abs(v - value)))
    return found


def _answer(
    setup: Setup, asked: Asked, system: list[Any], solutions: list[dict[Any, Any]]
) -> FormalValue | str:
    """The server's value for one asked part, or why there is none."""
    target = setup.symbols[asked.symbol]
    candidates = _target_values(solutions, target, setup.unknowns)
    if not candidates:
        return "no real solution"
    shown = in_unit(candidates, asked.unit)
    chosen = _choose(shown, asked.answer)
    if chosen is None:
        return "several solutions"
    if not _satisfies(system, solutions, target, candidates[shown.index(chosen)]):
        return "solution does not satisfy the equations"
    uses = _uses(setup, target)
    band = _band(setup, target, asked.unit, chosen, uses)
    low, high = min(band), max(band)
    agrees = None
    if asked.answer is not None:
        agrees = _close(asked.answer, chosen) or low <= asked.answer <= high
    return FormalValue(
        part=asked.part,
        symbol=asked.symbol,
        value=chosen,
        unit=asked.unit,
        low=low,
        high=high,
        uses=tuple(sorted(setup.written[s] for s in uses - setup.constants)),
        agrees=agrees,
    )


def solve_formal(problem_json: str, question: str) -> str:
    """The checked solution of the setup, as ``FormalResult`` JSON. Runs in the SymPy pool."""
    problem = FormalProblem.model_validate_json(problem_json)
    if not problem.solvable or not problem.equations or not problem.asked:
        return _refused("no setup")
    problem = _cleaned(problem)
    try:
        setup = _read_setup(problem, question)
        system, solutions = _solutions(setup, setup.values)
    except _Refused as refused:
        return _refused(str(refused))
    answers, reasons = [], []
    for asked in problem.asked:
        answer = _answer(setup, asked, system, solutions)
        if isinstance(answer, str):
            reasons.append(answer)
        else:
            answers.append(answer)
    conflicts = broken_checks(problem.checks, setup, solutions, answers)
    if not answers and not conflicts:
        return _refused(reasons[0] if reasons else "no real solution")
    return json.dumps(
        asdict(FormalResult(solved=True, answers=answers, conflicts=conflicts)), default=str
    )


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=AGREEMENT, abs_tol=1e-12)


def _choose(candidates: list[float], answer: float | None) -> float | None:
    """One value: the only one, the only positive one, or the one the model's answer names."""
    if len(candidates) == 1:
        return candidates[0]
    positive = [c for c in candidates if c > 0]
    if len(positive) == 1:
        return positive[0]
    if answer is not None:
        named = [c for c in candidates if _close(answer, c)]
        if len(named) == 1:
            return named[0]
    return None


def _satisfies(
    system: list[Any], solutions: list[dict[Any, Any]], target: Any, value: float
) -> bool:
    for solution in solutions:
        try:
            if not math.isclose(
                float(solution[target].evalf()), value, rel_tol=1e-9, abs_tol=1e-15
            ):
                continue
            for equation in system:
                residual = complex((equation.lhs - equation.rhs).subs(solution).evalf())
                size = max(1.0, abs(complex(equation.lhs.subs(solution).evalf())))
                if abs(residual) > _RESIDUAL * size:
                    break
            else:
                return True
        except (TypeError, ValueError, KeyError):
            continue
    return False
