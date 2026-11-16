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

The answer is in the unit the question asked for. Whether it agrees with the model's own
final answer is reported, not decided here: the caller chooses what a student sees.
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

from app.services.formal.constants import is_standard
from app.services.formal.problem import FormalProblem

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
    value: float | None = None
    unit: str = ""
    # The model's own answer agrees with the server's within ``AGREEMENT``; None without one.
    agrees: bool | None = None
    # Every real value the setup allows for the target, in ``unit``, before the choice.
    candidates: list[float] = field(default_factory=list)


def _refused(reason: str) -> str:
    return json.dumps(asdict(FormalResult(solved=False, reason=reason)))


def _registry() -> Any:
    from app.services.units import get_unit_registry

    return get_unit_registry()


def _unit_text(unit: str) -> str:
    text = unicodedata.normalize("NFKC", unit).strip()
    if not text:
        return "dimensionless"
    for old, new in (("°C", "degC"), ("ºC", "degC"), ("°F", "degF"), ("°", "degree")):
        text = text.replace(old, new)
    text = text.replace("²", "**2").replace("³", "**3").replace("^", "**")
    text = text.replace("·", "*").replace("Ω", "ohm").replace("µ", "u").replace("μ", "u")
    return text.replace("%", "percent")


def _quantity(value: float, unit: str) -> Any:
    registry = _registry()
    return registry.Quantity(value, _unit_text(unit))


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


def grounded(value: float, quote: str, question: str) -> bool:
    """The given's words are in the question and say its number. A count written in words
    ("two resistors", "dos resistencias") carries no digits: a whole number up to twelve
    is taken from words the question holds."""
    if not quote.strip() or _folded(quote) not in _folded(question):
        return False
    numbers = [parse_number(match.group()) for match in _NUMBER.finditer(quote)]
    if any(n is not None and math.isclose(n, value, rel_tol=1e-9) for n in numbers):
        return True
    return not numbers and float(value).is_integer() and 0 <= value <= 12


def _sympy_tree(node: ast.expr, symbols: dict[str, Any]) -> Any:
    import sympy

    functions = {
        "sqrt": sympy.sqrt,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "asin": sympy.asin,
        "acos": sympy.acos,
        "atan": sympy.atan,
        "exp": sympy.exp,
        "log": sympy.log,
        "abs": sympy.Abs,
    }
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return sympy.nsimplify(node.value) if isinstance(node.value, int) else node.value
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return sympy.pi
        if node.id not in symbols:
            if not node.id.isidentifier() or len(node.id) > _MAX_SYMBOL or len(symbols) > 40:
                raise ValueError(f"symbol {node.id}")
            symbols[node.id] = sympy.Symbol(node.id, real=True)  # declared by its equation
        return symbols[node.id]
    if isinstance(node, ast.UnaryOp):
        inner = _sympy_tree(node.operand, symbols)
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left, right = _sympy_tree(node.left, symbols), _sympy_tree(node.right, symbols)
        operations = {
            ast.Add: lambda: left + right,
            ast.Sub: lambda: left - right,
            ast.Mult: lambda: left * right,
            ast.Div: lambda: left / right,
            ast.Pow: lambda: left**right,
        }
        build = operations.get(type(node.op))
        if build is None:
            raise ValueError("operator")
        return build()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return functions[node.func.id](_sympy_tree(node.args[0], symbols))
    raise ValueError(f"{type(node).__name__} not allowed")


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
    return _sympy_tree(trees[0], symbols), _sympy_tree(trees[1], symbols)


_NUMPY_FUNCTIONS = ("sqrt", "sin", "cos", "tan", "exp", "log")
_NUMPY_INVERSE = {"asin": "arcsin", "acos": "arccos", "atan": "arctan"}


def _kind(expression: Any, units: dict[Any, Any]) -> Any:
    """The quantity ``expression`` is when each symbol is 1 of its unit (only its kind
    counts); pint raises when a sum mixes kinds or a function's argument has a unit."""
    import numpy as np
    import sympy

    registry = _registry()
    functions: dict[str, Any] = {name: getattr(np, name) for name in _NUMPY_FUNCTIONS}
    functions |= {name: getattr(np, inverse) for name, inverse in _NUMPY_INVERSE.items()}
    functions |= {"Abs": abs, "pi": math.pi}
    order = sorted(expression.free_symbols, key=str)
    value = sympy.lambdify(order, expression, modules=[functions])(
        *(registry.Quantity(1.0, units[symbol]) for symbol in order)
    )
    return value if hasattr(value, "dimensionality") else registry.Quantity(value)


def _dimensions_agree(sides: tuple[Any, Any], units: dict[Any, Any]) -> bool:
    """Both sides are the same kind of quantity; a side that is 0 is any kind."""
    try:
        kinds = [None if side == 0 else _kind(side, units) for side in sides]
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
                        units[alone] = _kind(other, units).to_base_units().units
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
            "target": _clean(problem.target),
        }
    )


def solve_formal(problem_json: str, question: str) -> str:
    """The checked solution of the setup, as ``FormalResult`` JSON. Runs in the SymPy pool."""
    import sympy

    problem = FormalProblem.model_validate_json(problem_json)
    if not problem.solvable or not problem.equations or not problem.target:
        return _refused("no setup")
    problem = _cleaned(problem)
    names = [g.symbol for g in problem.givens] + [u.symbol for u in problem.unknowns]
    if len(set(names)) != len(names) or any(
        not n.isidentifier() or len(n) > _MAX_SYMBOL or n in _RESERVED for n in names
    ):
        return _refused("symbols")
    registry = _registry()
    symbols = {n: sympy.Symbol(n, real=True) for n in names}
    values: dict[Any, float] = {}
    units: dict[Any, Any] = {}
    try:
        for given in problem.givens:
            number = parse_number(given.value)
            if number is None:
                return _refused(f"value of {given.symbol}")
            base = _quantity(number, given.unit).to_base_units()
            if given.constant:
                if not is_standard(base.magnitude, base.units, registry):
                    return _refused(f"constant {given.symbol} is no standard value")
            elif not grounded(number, given.quote, question):
                return _refused(f"{given.symbol} is not in the question")
            values[symbols[given.symbol]] = float(base.magnitude)
            units[symbols[given.symbol]] = base.units
        for unknown in problem.unknowns:
            units[symbols[unknown.symbol]] = _quantity(1.0, unknown.unit).to_base_units().units
        target_unit = _quantity(1.0, problem.target_unit or "")
    except Exception as exc:  # pint: a unit it cannot read
        logger.info("formal setup: unit not read (%s)", type(exc).__name__)
        return _refused(f"unit ({type(exc).__name__})")
    target = symbols.get(problem.target)
    unknowns = [symbols[u.symbol] for u in problem.unknowns]
    if target is None or target not in unknowns:
        return _refused("target is no unknown")
    if target_unit.to_base_units().dimensionality != units[target].dimensionality:
        return _refused("target unit")
    declared = set(symbols.values())
    try:
        equations = [_equation(text, symbols) for text in problem.equations]
    except Exception as exc:  # the tree refused it: not plain arithmetic
        logger.info("formal setup: equation refused (%s)", type(exc).__name__)
        return _refused(f"equation: {str(exc)[:60]}")
    extra = set(symbols.values()) - declared
    if not _infer_units(equations, units, extra):
        return _refused("a symbol no equation gives the kind of")
    unknowns += sorted(extra, key=str)
    if not all(_dimensions_agree(sides, units) for sides in equations):
        return _refused("units of an equation")
    system = [sympy.Eq(left.subs(values), right.subs(values)) for left, right in equations]
    try:
        solutions = sympy.solve(system, unknowns, dict=True)
    except Exception as exc:  # SymPy found no closed form
        logger.info("formal setup: not solved (%s)", type(exc).__name__)
        return _refused(f"solve ({type(exc).__name__})")
    candidates = _target_values(solutions if isinstance(solutions, list) else [], target, unknowns)
    if not candidates:
        return _refused("no real solution")
    scale = float(
        registry.Quantity(1.0, target_unit.to_base_units().units).to(target_unit.units).magnitude
    )
    shown = [c * scale for c in candidates]
    chosen = _choose(shown, problem.answer)
    if chosen is None:
        return json.dumps(
            asdict(FormalResult(solved=False, reason="several solutions", candidates=shown))
        )
    if not _satisfies(system, solutions, target, chosen / scale):
        return _refused("solution does not satisfy the equations")
    agrees = None if problem.answer is None else _close(problem.answer, chosen)
    unit = problem.target_unit or ""
    return json.dumps(
        asdict(FormalResult(solved=True, value=chosen, unit=unit, agrees=agrees, candidates=shown))
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
