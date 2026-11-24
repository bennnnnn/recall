"""How far a worked side may honestly be from its value: its inputs' own rounding, carried.

Working rounds as it goes: "25 \\times 0.8192 \\times 4.82" was worked on the exact cos 35°
and t, so its result may be anywhere the rounded 0.8192 and 4.82 allow, never further. The
side is walked over ranges, each rounded number standing for every value that rounds to it
("4.82" is 4.815 to 4.825), and the result's range is how far rounding alone moves it. A
result outside it is a slip, however small (live, 2026-11-23: sqrt(1088.5) written 33.11,
0.4% off its 32.99). Which numbers are rounded the caller says: a given is exact.

The same walk as ``tex_arithmetic.evaluate``: nothing is eval-ed, powers are capped.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable

from app.modules.chat.tex_arithmetic import CALLS, CONSTANTS, evaluate, in_domain, power

Range = tuple[float, float]


def spread(
    expression: str, rounded: Callable[[str], bool], *, natural_log: bool = False
) -> float | None:
    """How far rounding alone may move ``expression``'s value: its range's widest side.
    ``rounded``: a number, as written, that stands for a range (half its last place
    either side); any other is exact. None when the side has no range (a division by a
    range around 0, a power of a range around 0). ``natural_log``: a log with no base is
    ln (``tex_arithmetic.log_readings``)."""
    value = evaluate(expression, natural_log=natural_log)
    try:
        tree = ast.parse(expression, mode="eval")
        span = _walk(tree.body, expression, rounded, natural_log)
    except (ArithmeticError, ValueError, SyntaxError):
        return None
    if value is None or span is None or not all(map(math.isfinite, span)):
        return None
    return max(span[1] - value, value - span[0], 0.0)


def half_place(number: str) -> float:
    """Half the last place a number is written to: "4.82" → 0.005, "1.6e-19" → 5e-21."""
    mantissa, _e, power_text = number.lower().partition("e")
    decimals = len(mantissa.partition(".")[2])
    return 0.5 * 10.0 ** (int(power_text or 0) - decimals)


def _walk(
    node: ast.AST, source: str, rounded: Callable[[str], bool], natural_log: bool
) -> Range | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        text = ast.get_source_segment(source, node) or ""
        width = half_place(text) if "." in text and rounded(text) else 0.0
        return float(node.value) - width, float(node.value) + width
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id], CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = _walk(node.operand, source, rounded, natural_log)
        if inner is None or isinstance(node.op, ast.UAdd):
            return inner
        return -inner[1], -inner[0]
    if isinstance(node, ast.BinOp):
        left = _walk(node.left, source, rounded, natural_log)
        right = _walk(node.right, source, rounded, natural_log)
        if left is None or right is None:
            return None
        return _binary(node.op, left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in CALLS:
        if len(node.args) != 1 or node.keywords:
            return None
        inner = _walk(node.args[0], source, rounded, natural_log)
        return None if inner is None else _call(node, inner, natural_log)
    return None


def _binary(op: ast.operator, left: Range, right: Range) -> Range | None:
    if isinstance(op, ast.Add):
        return left[0] + right[0], left[1] + right[1]
    if isinstance(op, ast.Sub):
        return left[0] - right[1], left[1] - right[0]
    if isinstance(op, ast.Mult):
        return _bounds([a * b for a in left for b in right])
    if isinstance(op, ast.Div):
        if right[0] <= 0 <= right[1]:
            return None
        return _bounds([a / b for a in left for b in right])
    if isinstance(op, ast.Pow):
        return _power_range(left, right)
    return None


def _power_range(base: Range, exponent: Range) -> Range | None:
    if base[0] < 0 < base[1] and not (exponent[0] == exponent[1] and exponent[0] >= 0):
        return None
    corners = [power(b, e) for b in base for e in exponent]
    if any(corner is None for corner in corners):
        return None
    low, high = _bounds([corner for corner in corners if corner is not None])
    if base[0] < 0 < base[1] and float(exponent[0]).is_integer() and exponent[0] % 2 == 0:
        low = 0.0
    return low, high


def _call(node: ast.Call, inner: Range, natural_log: bool) -> Range | None:
    """A function over a range: its ends and middle (the ranges are rounding-small, so a
    sine's turn inside one moves it by nothing a step could show)."""
    name = node.func.id if isinstance(node.func, ast.Name) else ""
    points = (inner[0], (inner[0] + inner[1]) / 2, inner[1])
    if not all(in_domain(node, point) for point in points):
        return None
    if name in ("tand", "rtan"):
        cosine = CALLS["cosd" if name == "tand" else "rcos"]
        if cosine(inner[0]) * cosine(inner[1]) <= 0:
            return None
    function = math.log if name == "lgx" and natural_log else CALLS[name]
    return _bounds([function(point) for point in points])


def _bounds(values: list[float]) -> Range:
    return min(values), max(values)
