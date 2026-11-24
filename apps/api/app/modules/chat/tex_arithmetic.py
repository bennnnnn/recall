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
from typing import Any, Literal, overload

from app.services.glyphs import fold_operator_glyphs
from app.services.md_fence_scan import iter_fences

_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MIXED_NUMBER = re.compile(r"\d\s*\\[dt]?frac\b")
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
# The names a plain side may call, longest first: "sind" is a sine of degrees, "rsin" one
# of radians; "lgx" a log with no base written (base 10, or e: ``log_readings``).
_FUNCTIONS = r"sqrt|pi|sind|cosd|tand|rsin|rcos|rtan|lgx|lg|lbin|ln|exp|euler"
# ln 2, \\log_{10} 1000, \\sin 0.5: a function of one bare number, its brackets left out.
_BARE_ARGUMENT = re.compile(
    r"\\(ln|log|exp|sin|cos|tan)(\s*_\s*\{?\s*(?:10|2|e)\s*\}?)?\s+(-?\d+(?:\.\d+)?)(?![\d.]|\s*\^)"
)
_LOG_BASE = re.compile(r"\\log\s*_\s*\{?\s*(10|2|e)\s*\}?")
_FUNCTION_NAMES = {"ln": "ln", "exp": "exp", "sin": "rsin", "cos": "rcos", "tan": "rtan"}
_NAMED_FUNCTION = re.compile(r"\\(ln|exp|sin|cos|tan|log)(?![A-Za-z])(?!\s*_)")
# Euler's number: \\mathrm{e}, or an e raised to a power with no letter before it.
_EULER = re.compile(r"\\(?:mathrm|text|rm)\s*\{\s*e\s*\}|(?<![A-Za-z\\])e(?=\s*\^)")
# A power of e that is e's own: a decimal or a sign in it ("e^{-0.5}", "e^{1.2}").
_EULER_POWER = re.compile(r"\s*\^\s*\{[^{}]*[.\-\\]")
# \\sqrt[3]{27}: a root of another degree.
_NTH_ROOT = re.compile(r"\\sqrt\s*\[\s*(\d+)\s*\]\s*\{([^{}]*)\}")
# A unit written out: never \\operatorname, which names a function (\\operatorname{ln}(2) is
# ln 2, not 2; review, #2520).
UNIT_GROUP = re.compile(r"\\(?:text|mathrm|textrm|rm)\s*\{[^{}]*\}(?:\s*\^\s*(?:\{[^{}]*\}|-?\d))?")
_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_POWER = re.compile(r"\^\s*\{([^{}]*)\}")
# "l_{maj} = 2(10) = 20, l_{min} = 2(6) = 12": two statements in one line, each its own chain.
# A real comma (never "\\," or 1,500) or a \\quad, then a name and its "=".
_STATEMENTS = re.compile(r"(?:(?<!\\),\s+|;\s*|\\q?quad\s*)(?=[A-Za-z\\][^,;=]{0,40}=)")
MAX_EXPONENT = 64


def plain_arithmetic(tex: str) -> str | None:
    """A LaTeX side as a Python arithmetic expression, or None when it is not numbers."""
    # "1\\frac{1}{2}" is a mixed number, one and a half, never one times a half: no
    # arithmetic is read for it (review, #2520).
    if _MIXED_NUMBER.search(tex):
        return None
    text = tex.replace("\\left", "").replace("\\right", "")
    text = _SCIENTIFIC.sub(r"(\1e\2)", text)
    text = _TRIG_DEGREES.sub(r" \1d(\2)", text)
    text = _named_functions(text)
    text = re.sub(r"\\pi(?![A-Za-z])", " pi ", text)
    text = _TEXT_WORD.sub(lambda m: m.group(0) if _is_unit(m.group(0)) else "#", text)
    text = UNIT_GROUP.sub(" ", text)
    for _ in range(4):
        text = _FRAC.sub(r"((\1)/(\2))", text)
        text = _NTH_ROOT.sub(r"((\2)**(1/(\1)))", text)
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
        rf"(?<=[\d)])(?=\(|{_FUNCTIONS})|(?<=\))(?=\d)|(?<=pi|er)(?=[\d(]|{_FUNCTIONS})",
        "*",
        text,
    )
    return text


def _named_functions(text: str) -> str:
    """ln, log, exp, sin, cos and tan as the names a plain side calls (``_FUNCTIONS``); a
    bare number after one is its argument ("\\ln 2" is ln(2)). A log of another base than
    10, 2 or e stays as written, so the side is not read."""
    text = _EULER.sub(lambda m: " euler " if _is_euler(text, m) else m.group(0), text)
    text = _BARE_ARGUMENT.sub(lambda m: f"\\{m.group(1)}{m.group(2) or ''}({m.group(3)})", text)
    text = _LOG_BASE.sub(lambda m: {"10": " lg ", "2": " lbin ", "e": " ln "}[m.group(1)], text)
    return _NAMED_FUNCTION.sub(lambda m: f" {_FUNCTION_NAMES.get(m.group(1), 'lgx')} ", text)


def _is_euler(text: str, match: re.Match[str]) -> bool:
    """An e that is Euler's number: written upright, after a number or an operation ("100
    e^{2}"), or raised to a decimal or a negative power. "e^2" alone is a name squared (an
    eccentricity, a charge), never 7.39."""
    if match.group(0) != "e" or text[: match.start()].strip():
        return True
    return _EULER_POWER.match(text, match.end()) is not None


def plain_branches(tex: str) -> list[str] | None:
    """A side with one ± as its two plain sides, + first ("\\frac{4 \\pm 2}{2}" is "(4+2)/2"
    and "(4-2)/2"); a side without one as itself. None when it is not numbers."""
    signs = re.findall(r"\\pm|\\mp|\u00b1|\u2213", tex)
    if len(signs) > 1:
        return None
    if not signs:
        plain = plain_arithmetic(tex)
        return [plain] if plain is not None else None
    first, second = ("+", "-") if signs[0] in ("\\pm", "\u00b1") else ("-", "+")
    sides = [plain_arithmetic(tex.replace(signs[0], sign, 1)) for sign in (first, second)]
    return [side for side in sides if side is not None] if all(sides) else None


# The SI symbols of one or two letters, beside the longer unit words.
_SI_SYMBOLS = frozenset(
    {"m", "s", "g", "A", "V", "W", "J", "N", "K", "L", "C", "F", "T", "h", "Pa", "Hz", "Ω"}
)


def is_unit_word(word: str) -> bool:
    """``word`` is a unit's symbol or short name ("cm", "kJ", "m", "Ω")."""
    return word in _UNIT_WORDS or word in _SI_SYMBOLS


def _is_unit(text_group: str) -> bool:
    inner = text_group[text_group.index("{") + 1 : -1].strip()
    return inner in _UNIT_WORDS


def evaluate(expression: str, *, natural_log: bool = False) -> float | None:
    """``expression`` worked out, or None. ``natural_log``: a log with no base written is ln,
    not the base-10 log school working means by it (``log_readings``)."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    try:
        value = _walk(tree.body, natural_log)
    except (ArithmeticError, ValueError):
        return None
    return value if value is not None and math.isfinite(value) else None


def log_readings(expression: str) -> list[float]:
    """The values ``expression`` may mean: a log with no base is base 10 in school working
    (pH, decibels) and e in calculus, so it has both; anything else has one."""
    values = [evaluate(expression)]
    if "lgx(" in expression:
        values.append(evaluate(expression, natural_log=True))
    return [value for value in values if value is not None]


def _walk(node: ast.AST, natural_log: bool = False) -> float | None:

    def walk(child: ast.AST) -> float | None:
        return _walk(child, natural_log)

    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        operand = walk(node.operand)
        if operand is None:
            return None
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp):
        left, right = walk(node.left), walk(node.right)
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
            return power(left, right)
        return None
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in CALLS
        and len(node.args) == 1
        and not node.keywords
    ):
        inner = walk(node.args[0])
        if inner is None or not in_domain(node, inner):
            return None
        if node.func.id == "lgx" and natural_log:
            return math.log(inner)
        return CALLS[node.func.id](inner)
    return None


def _sind(degrees: float) -> float:
    return math.sin(math.radians(degrees))


def _cosd(degrees: float) -> float:
    return math.cos(math.radians(degrees))


def _tand(degrees: float) -> float:
    return math.tan(math.radians(degrees))


def power(base: float, exponent: float) -> float | None:
    """``base ** exponent`` with the exponent capped; an odd root of a negative number is
    negative (the cube root of -8 is -2), any other fractional power of one is not read."""
    if abs(exponent) > MAX_EXPONENT:
        return None
    if base < 0 and not float(exponent).is_integer():
        degree = 1 / exponent if exponent else 0.0
        if not (math.isclose(degree, round(degree)) and round(degree) % 2 == 1):
            return None
        return -float((-base) ** exponent)
    return float(base**exponent)


# A sine of radians past a full turn is degrees with the sign left out ("\\sin(30)"): not read.
_FULL_TURN = 2 * math.pi + 1e-9
# e^x past this is no school number, and is not worked out.
_MAX_EXP = 150.0


def in_domain(node: ast.Call, inner: float) -> bool:
    name = node.func.id if isinstance(node.func, ast.Name) else ""
    if name == "sqrt":
        return inner >= 0
    if name in ("ln", "lg", "lgx", "lbin"):
        return inner > 0
    if name == "exp":
        return abs(inner) <= _MAX_EXP
    if name in ("rsin", "rcos", "rtan"):
        return abs(inner) <= _FULL_TURN or _names_pi(node.args[0])
    return True


def _names_pi(node: ast.AST) -> bool:
    return any(isinstance(sub, ast.Name) and sub.id == "pi" for sub in ast.walk(node))


CONSTANTS = {"pi": math.pi, "euler": math.e}
CALLS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "sind": _sind,
    "cosd": _cosd,
    "tand": _tand,
    "rsin": math.sin,
    "rcos": math.cos,
    "rtan": math.tan,
    "ln": math.log,
    "lg": math.log10,
    "lgx": math.log10,
    "lbin": math.log2,
    "exp": math.exp,
}


@overload
def math_statements(reply: str) -> Iterator[str]: ...
@overload
def math_statements(reply: str, *, with_breaks: Literal[True]) -> Iterator[tuple[str, bool]]: ...
def math_statements(reply: str, *, with_breaks: bool = False) -> Iterator[Any]:
    """Each statement of the reply's inline maths, in reading order: never one in a code fence
    or inline code, and a line of two ("I_1 = 2, I_2 = 3") read as two. ``with_breaks``: each
    with whether it follows the one before directly, only space between them."""
    for statement, follows, _start in math_statement_spans(reply):
        yield (statement, follows) if with_breaks else statement


def math_statement_spans(reply: str) -> Iterator[tuple[str, bool, int]]:
    """``math_statements`` with breaks, each with where it starts in ``reply``."""
    prose = _masked(reply)
    end: int | None = None
    for match in INLINE_MATH.finditer(prose):
        follows = end is not None and not prose[end : match.start()].strip()
        end = match.end()
        inside, start = match.group(1), match.start(1)
        cuts = [0, *(cut for split in _STATEMENTS.finditer(inside) for cut in split.span())]
        cuts.append(len(inside))
        for index in range(0, len(cuts), 2):
            yield inside[cuts[index] : cuts[index + 1]], follows or index > 0, start + cuts[index]


def _masked(reply: str) -> str:
    """``reply`` with each closed code fence and inline code blanked, every offset kept."""
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(reply):
        if fence.closed:
            pieces += [reply[cursor : fence.start], _blank(reply[fence.start : fence.end])]
            cursor = fence.end
    pieces.append(reply[cursor:])
    return _INLINE_CODE.sub(lambda m: _blank(m.group(0)), "".join(pieces))


def prose_only(reply: str) -> str:
    """``reply`` with its fences, inline code and inline maths blanked, every offset kept."""
    return INLINE_MATH.sub(lambda m: _blank(m.group(0)), _masked(reply))


def _blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)
