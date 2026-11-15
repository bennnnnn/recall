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
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import app.modules.math.solve.shape_formulas as formulas
from app.modules.math.drawing.question import Question
from app.modules.math.figure.grounding import unit_name

Amounts = Callable[[Sequence[Any], bool], dict[str, Any]]


def _pi() -> Any:
    import sympy

    return sympy.pi


def _ends(lid: bool) -> int:
    return 2 if lid else 1


def _slant(r: Any, h: Any) -> Any:
    import sympy

    return sympy.sqrt(r**2 + h**2)


# Each shape's amounts in its free sizes (``shapes.FORMS``' order); ``lid``: closed. The
# formulas are the solver's own (``solve.shape_formulas``).
AMOUNTS: dict[str, Amounts] = {
    "window": lambda s, _lid: {
        "perimeter": 2 * s[0] + 2 * s[1] + _pi() * s[0],
        "area": 2 * s[0] * s[1] + _pi() * s[0] ** 2 / 2,
    },
    "rectangle": lambda s, _lid: formulas.rectangle(s[0], s[1]),
    "square": lambda s, _lid: formulas.square(s[0]),
    "circle": lambda s, _lid: formulas.circle(s[0], _pi()),
    "cylinder": lambda s, lid: formulas.cylinder(s[0], s[1], _pi(), _ends(lid)),
    "cone": lambda s, _lid: formulas.cone(s[0], s[1], _pi(), _slant(s[0], s[1])),
    "sphere": lambda s, _lid: formulas.sphere(s[0], _pi()),
    "box": lambda s, lid: formulas.cuboid(s[0], s[1], s[2], _ends(lid)),
    "sheet": lambda s, _lid: {"volume": (s[0] - 2 * s[2]) * (s[1] - 2 * s[2]) * s[2]},
    "inscribed:cone": lambda s, _lid: {"volume": _pi() * s[2] ** 2 * s[1] * (1 - s[2] / s[0])},
}

# A stated number and the unit the question writes after it: "500 cm³", "48 square units",
# "12 m of framing", "a 10-litre can", "500 ml", "20 m^2".
# Read on text whose whitespace runs are one space (``_one_space``): single optional spaces
# cannot backtrack, where "\s*-?\s*" did at degree 3 (CI's slow-regex gate on #2462).
_STATED = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d.]) ?-? ?(?:(cubic|cu\.?|square|sq\.?) )?([a-z]+)?"
    r" ?(²|³|\^ ?2|\^ ?3)?"
)
_SPACES = re.compile(r"\s+")
_LITRES = {"l": 1000.0, "litre": 1000.0, "litres": 1000.0, "liter": 1000.0, "liters": 1000.0,
           "ml": 1.0, "millilitre": 1.0, "millilitres": 1.0, "milliliter": 1.0,
           "milliliters": 1.0}  # fmt: skip
_UNITS = frozenset({"unit", "units"})
# What each amount is measured as.
_KIND = {"volume": "volume", "surface": "area", "area": "area", "perimeter": "length"}


def _stated(written: re.Match[str]) -> tuple[str, float, str] | None:
    """What a stated number measures as the question writes it ("volume", "area" or
    "length"), its scale to the drawing's unit of length cubed (a litre is 1000 cm³) and
    that unit; None for a bare number, which says none of them."""
    power, word, mark = written.group(2) or "", (written.group(3) or "").lower(), written.group(4)
    mark = (mark or "").replace(" ", "")
    if word in _LITRES and not power and not mark:
        return "volume", _LITRES[word], "cm"
    unit = "" if word in _UNITS else unit_name(word)
    if not unit and word not in _UNITS:
        return None
    if power.startswith(("cubic", "cu")) or mark in {"³", "^3"}:
        return "volume", 1.0, unit
    if power.startswith(("square", "sq")) or mark in {"²", "^2"}:
        return "area", 1.0, unit
    return ("length", 1.0, unit) if word not in _UNITS else None


def _readings(question: Question) -> dict[float, set[tuple[str, float, str]]]:
    """Each number the question states with a unit, and what that unit says it measures."""
    found: dict[float, set[tuple[str, float, str]]] = {}
    for text in question.texts:
        for written in _STATED.finditer(_SPACES.sub(" ", text.lower())):
            reading = _stated(written)
            if reading is not None:
                found.setdefault(float(written.group(1)), set()).add(reading)
    return found


def read_amount(kind: str, text: str, question: Question) -> tuple[float, str] | None:
    """A fixed amount as the question states it: its value in the drawing's unit of length
    (cubed or squared) and that unit; None when the question states no such amount. What it
    measures is read from the question's own unit, never the description's: round 2's
    review fed "500 cm³" in as a surface. A bare number ("an area of 48") says no unit, and
    is left out."""
    found = re.match(r"^\s*(\d+(?:\.\d+)?)", str(text))
    if found is None or kind not in _KIND:
        return None
    value = float(found.group(1))
    readings = next((r for v, r in _readings(question).items() if abs(v - value) < 1e-9), set())
    if value <= 0 or len(readings) != 1:
        return None
    measured, scale, unit = next(iter(readings))
    return (value * scale, unit) if measured == _KIND[kind] else None


def stated_amounts(question: Question, kinds: Iterable[str]) -> list[tuple[str, float, str]]:
    """Every amount of ``kinds`` the question states, as ``read_amount`` reads it: each
    kind with its value in the drawing's unit and that unit ("12 m of framing": a
    perimeter of 12 m)."""
    found = []
    for value, readings in _readings(question).items():
        if value <= 0 or len(readings) != 1:
            continue
        measured, scale, unit = next(iter(readings))
        found += [(kind, value * scale, unit) for kind in kinds if _KIND.get(kind) == measured]
    return found


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
