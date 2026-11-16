"""The school formulas for a shape's amounts, written once.

Each takes its sizes and π as numbers (the solver's ``math.pi``) or as SymPy symbols and
``sympy.pi`` (a drawn word problem's sizes, solved for its best: ``drawing.amounts``), so
the answer the solver gives and the sizes a figure is drawn at come from one formula.
``ends``: how many of a can's or a box's ends it has, 2 closed, 1 with no lid.
"""

from __future__ import annotations

from typing import Any

Amounts = dict[str, Any]


def rectangle(w: Any, h: Any) -> Amounts:
    return {"area": w * h, "perimeter": 2 * (w + h)}


def square(s: Any) -> Amounts:
    return {"area": s * s, "perimeter": 4 * s}


def circle(r: Any, pi: Any) -> Amounts:
    return {"area": pi * r * r, "perimeter": 2 * pi * r}


def cylinder(r: Any, h: Any, pi: Any, ends: int = 2) -> Amounts:
    surface = 2 * pi * r * (r + h) if ends == 2 else pi * r * r + 2 * pi * r * h
    return {"volume": pi * r * r * h, "surface": surface}


def cone(r: Any, h: Any, pi: Any, slant: Any) -> Amounts:
    return {"volume": pi * r * r * h / 3, "surface": pi * r * (r + slant)}


def sphere(r: Any, pi: Any) -> Amounts:
    return {"volume": 4 * pi * r * r * r / 3, "surface": 4 * pi * r * r}


def cuboid(length: Any, w: Any, h: Any, ends: int = 2) -> Amounts:
    if ends == 2:
        surface = 2 * (length * w + length * h + w * h)
    else:
        surface = length * w + 2 * h * (length + w)
    return {"volume": length * w * h, "surface": surface}
