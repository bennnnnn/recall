"""A word problem's stated amount and what it asks to make best, worked out by the server.

"12 m of framing round a window: the most light", "a 10-litre can of least metal", "an open
box of 48 square units holding the most": the description names the amount the question
fixes (with its value as the question writes it) and the amount to make largest or
smallest; the shape's own formulas say what each amount is in its sizes. SymPy solves for
the one size left free and takes the critical point that is a maximum or a minimum, and the
figure is drawn, and labelled, at those sizes (owner decision 2026-11-15: a value the server
works out and checks may be labelled; the model's own number never is).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from app.modules.math.drawing.question import Question
from app.modules.math.figure.grounding import unit_name

Amounts = Callable[[Sequence[Any], bool], dict[str, Any]]


def _pi() -> Any:
    import sympy

    return sympy.pi


def _round(r: Any, h: Any, lid: bool) -> dict[str, Any]:
    pi = _pi()
    return {
        "volume": pi * r**2 * h,
        "surface": (2 if lid else 1) * pi * r**2 + 2 * pi * r * h,
    }


# Each shape's amounts in its free sizes (``shapes.FORMS``' order); ``lid``: closed.
AMOUNTS: dict[str, Amounts] = {
    "window": lambda s, _lid: {
        "perimeter": 2 * s[0] + 2 * s[1] + _pi() * s[0],
        "area": 2 * s[0] * s[1] + _pi() * s[0] ** 2 / 2,
    },
    "rectangle": lambda s, _lid: {"perimeter": 2 * (s[0] + s[1]), "area": s[0] * s[1]},
    "square": lambda s, _lid: {"perimeter": 4 * s[0], "area": s[0] ** 2},
    "circle": lambda s, _lid: {"perimeter": 2 * _pi() * s[0], "area": _pi() * s[0] ** 2},
    "cylinder": lambda s, lid: _round(s[0], s[1], lid),
    "cone": lambda s, _lid: {"volume": _pi() * s[0] ** 2 * s[1] / 3},
    "sphere": lambda s, _lid: {
        "volume": 4 * _pi() * s[0] ** 3 / 3,
        "surface": 4 * _pi() * s[0] ** 2,
    },
    "box": lambda s, lid: {
        "volume": s[0] * s[1] * s[2],
        "surface": (2 if lid else 1) * s[0] * s[1] + 2 * s[2] * (s[0] + s[1]),
    },
    "sheet": lambda s, _lid: {"volume": (s[0] - 2 * s[2]) * (s[1] - 2 * s[2]) * s[2]},
    "inscribed:cone": lambda s, _lid: {"volume": _pi() * s[2] ** 2 * s[1] * (1 - s[2] / s[0])},
}

_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(.*?)\s*\.?$")
# The words and marks that say an amount is an area or a volume, and the unit of length it
# is drawn in: "48 square units", "12 m²", "10 litres" (1000 cm³ each), "500 ml".
_AREA = re.compile(r"^(?:square|sq\.?)\s+(\w+)$|^(\w+?)\s*(?:²|\^2|2)$")
_VOLUME = re.compile(r"^(?:cubic|cu\.?)\s+(\w+)$|^(\w+?)\s*(?:³|\^3|3)$")
_LITRES = {"l": 1000.0, "litre": 1000.0, "litres": 1000.0, "liter": 1000.0, "liters": 1000.0,
           "ml": 1.0, "millilitre": 1.0, "millilitres": 1.0, "milliliter": 1.0,
           "milliliters": 1.0}  # fmt: skip
_BARE = frozenset({"unit", "units", ""})


def _length_unit(word: str) -> str | None:
    word = word.lower()
    return "" if word in _BARE else (unit_name(word) or None)


def read_amount(kind: str, text: str, question: Question) -> tuple[float, str] | None:
    """A fixed amount as the question states it: its value in the drawing's unit of length
    (cubed or squared) and that unit; None when the question states no such amount."""
    found = _NUMBER.match(" ".join(str(text).split()))
    if found is None:
        return None
    value, unit_text = float(found.group(1)), found.group(2).lower()
    stated = any(
        not w.in_formula and abs(float(w.value) - value) < 1e-9 and w.unit != "deg"
        for w in question.numbers
    )
    if not stated or value <= 0:
        return None
    if kind == "perimeter":
        unit = _length_unit(unit_text)
        return None if unit is None else (value, unit)
    if kind == "volume" and unit_text in _LITRES:
        return value * _LITRES[unit_text], "cm"
    shape = (_AREA if kind == "area" or kind == "surface" else _VOLUME).match(unit_text)
    if shape is None:
        return (value, "") if unit_text in _BARE else None
    unit = _length_unit(shape.group(1) or shape.group(2) or "")
    return None if unit is None else (value, unit)


def optimum(
    symbols: Sequence[Any], equations: list[Any], objective: Any, goal: str
) -> list[float] | None:
    """The sizes that meet ``equations`` and make ``objective`` largest ("max") or smallest
    ("min"): one size left free, its one critical point of that kind; None otherwise."""
    import sympy

    for free in symbols:
        others = [symbol for symbol in symbols if symbol is not free]
        found = sympy.solve(equations, others, dict=True) if others else [{}]
        if len(found) != 1 or len(found[0]) != len(others):
            continue
        rest = found[0]
        f = sympy.simplify(objective.subs(rest))
        if f.free_symbols != {free}:
            continue
        points = [p for p in sympy.solve(sympy.diff(f, free), free) if p.is_real and p > 0]
        bend = sympy.diff(f, free, 2)
        kept = [p for p in points if (bend.subs(free, p) < 0) == (goal == "max")]
        if len(kept) != 1:
            return None
        at = {free: kept[0], **{k: v.subs(free, kept[0]) for k, v in rest.items()}}
        values = [float(at[symbol]) for symbol in symbols]
        return values if all(v > 0 for v in values) else None
    return None
