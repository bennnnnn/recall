"""LaTeX arithmetic as plain numbers: a side of working read and worked out, never eval-ed.

Shared by the working check (one line's arithmetic) and the systems check (values put back
into the equations they solve). ``plain_arithmetic`` turns a LaTeX side into a Python
expression of numbers, or None when it holds a letter, a word or a unit it cannot drop;
``evaluate`` walks that expression with powers capped, so a reply cannot make the server
compute a huge number.
"""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable, Iterator

from app.services.glyphs import fold_operator_glyphs
from app.services.md_fence_scan import map_fence_blocks

_INLINE_CODE = re.compile(r"`[^`\n]*`")
INLINE_MATH = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)")
# 3.98 \times 10^{-19} is one number: "a * 10^-19 / b * 10^-19" divides two of them.
_SCIENTIFIC = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\\times|\\cdot|\u00d7|\*)\s*10\s*\^\s*\{?\s*([-+]?\d+)\s*\}?"
)
# A word inside \text{} ("and", "for x = 3") joins two statements; it is not a unit.
_TEXT_WORD = re.compile(r"\\text\s*\{\s*[A-Za-z]{2,}(?:\s+[A-Za-z]+)*\s*\}")
_UNIT_WORDS = frozenset(
    {
        "kg",
        "mol",
        "cm",
        "mm",
        "km",
        "ms",
        "min",
        "hr",
        "Hz",
        "kHz",
        "MHz",
        "Pa",
        "kPa",
        "atm",
        "mL",
        "kJ",
        "MJ",
        "kW",
        "MW",
        "kWh",
        "eV",
        "keV",
        "MeV",
        "nm",
        "rad",
        "deg",
        "mph",
        "ft",
        "in",
        "lb",
        "lbs",
        "psi",
        "mmHg",
        "torr",
        "cal",
        "kcal",
        "Wh",
        "mA",
        "kV",
        "mV",
        "kN",
        "GW",
        "GJ",
        "mg",
        "ug",
    }
)
# sin 75°, \sin(60^\circ): a sine of degrees, the one function of an angle working writes.
_TRIG_DEGREES = re.compile(
    r"\\(sin|cos|tan)\s*\(?\s*(-?\d+(?:\.\d+)?)\s*(?:°|\^\s*\{?\s*\\circ\s*\}?)\s*\)?"
)
_FUNCTIONS = r"sqrt|pi|sind|cosd|tand"
UNIT_GROUP = re.compile(
    r"\\(?:text|mathrm|textrm|rm|operatorname)\s*\{[^{}]*\}(?:\s*\^\s*(?:\{[^{}]*\}|-?\d))?"
)
_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_POWER = re.compile(r"\^\s*\{([^{}]*)\}")
# "l_{maj} = 2(10) = 20, l_{min} = 2(6) = 12": two statements in one line, each its own chain.
# A real comma (never "\\," or 1,500) or a \\quad, then a name and its "=".
_STATEMENTS = re.compile(r"(?:(?<!\\),\s+|;\s*|\\q?quad\s*)(?=[A-Za-z\\][^,;=]{0,40}=)")
MAX_EXPONENT = 64


def plain_arithmetic(tex: str) -> str | None:
    """A LaTeX side as a Python arithmetic expression, or None when it is not numbers."""
    text = tex.replace("\\left", "").replace("\\right", "")
    text = _SCIENTIFIC.sub(r"(\1e\2)", text)
    text = _TRIG_DEGREES.sub(r" \1d(\2)", text)
    text = re.sub(r"\\pi(?![A-Za-z])", " pi ", text)
    text = _TEXT_WORD.sub(lambda m: m.group(0) if _is_unit(m.group(0)) else "#", text)
    text = UNIT_GROUP.sub(" ", text)
    for _ in range(4):
        text = _FRAC.sub(r"((\1)/(\2))", text)
        text = _SQRT.sub(r"sqrt(\1)", text)
        text = _POWER.sub(r"**(\1)", text)
    text = fold_operator_glyphs(text)
    for latex, plain in (
        ("\\times", "*"),
        ("\\cdot", "*"),
        ("\\div", "/"),
        ("\\,", ""),
        ("\\;", ""),
        ("\\!", ""),
        ("\\ ", ""),
        ("{,}", ""),
    ):
        text = text.replace(latex, plain)
    text = text.replace("^", "**").replace("{", "(").replace("}", ")")
    text = re.sub(r"\s+", "", text)
    # 1,500 is a number; a comma anywhere else is a list.
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    letters = re.sub(rf"{_FUNCTIONS}|(?<=\d)e(?=[-+]?\d)", "", text)
    if not text or re.search(r"[A-Za-z\\%°',#]", letters):
        return None
    # 2(3), (2)(3), 25sqrt(73), 2pi, pi(3): a product written without a sign.
    text = re.sub(
        rf"(?<=[\d)])(?=\(|{_FUNCTIONS})|(?<=\))(?=\d)|(?<=pi)(?=[\d(]|{_FUNCTIONS})", "*", text
    )
    return text


def _is_unit(text_group: str) -> bool:
    inner = text_group[text_group.index("{") + 1 : -1].strip()
    return inner in _UNIT_WORDS


def evaluate(expression: str) -> float | None:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    try:
        value = _walk(tree.body)
    except (ArithmeticError, ValueError):
        return None
    return value if value is not None and math.isfinite(value) else None


def _walk(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        operand = _walk(node.operand)
        if operand is None:
            return None
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp):
        left, right = _walk(node.left), _walk(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT or (left < 0 and not float(right).is_integer()):
                return None
            return float(left**right)
        return None
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _CALLS
        and len(node.args) == 1
        and not node.keywords
    ):
        inner = _walk(node.args[0])
        if inner is None or (node.func.id == "sqrt" and inner < 0):
            return None
        return _CALLS[node.func.id](inner)
    return None


def _sind(degrees: float) -> float:
    return math.sin(math.radians(degrees))


def _cosd(degrees: float) -> float:
    return math.cos(math.radians(degrees))


def _tand(degrees: float) -> float:
    return math.tan(math.radians(degrees))


_CALLS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "sind": _sind,
    "cosd": _cosd,
    "tand": _tand,
}


def math_statements(reply: str) -> Iterator[str]:
    """Each statement of the reply's inline maths, in reading order: never one in a code fence
    or inline code, and a line of two ("I_1 = 2, I_2 = 3") read as two."""
    prose = _INLINE_CODE.sub(" ", map_fence_blocks(reply, lambda _fence, _body: "\n"))
    for match in INLINE_MATH.finditer(prose):
        yield from _STATEMENTS.split(match.group(1))
