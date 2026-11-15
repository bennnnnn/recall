"""A word problem's figure: each shape's sizes, worked out from its labels.

A shape has a few free sizes (a window: the radius of its semicircle and the height of its
rectangle) and parts whose lengths follow from them (its width is twice the radius). The
labels pin what they can: a stated value fixes its part's length, one letter on two parts
makes them equal, and a multiple the question writes ("h = 3r") fixes their ratio. What is
left open is drawn in a representative proportion, scaled to the stated values, and carries
only its letter, never a number. SymPy solves for the sizes; the build runs in the pool.

A multiple the question does not write ("2r") is shown only where the shape itself makes it
true: on a window's width beside its radius "r", never on a can's height, where "h = 2r"
is the optimisation's answer and not the question's.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.math.drawing.labels import Label

_TOLERANCE = 1e-9


def _always(_sizes: Sequence[float]) -> bool:
    return True


@dataclass(frozen=True)
class Form:
    """One shape: the shapes the question must name for it (``figure.shape_names``), its
    free sizes in a representative proportion, each part's length in those sizes, and the
    sizes it can be drawn with."""

    named: tuple[str, ...]
    sizes: tuple[float, ...]
    parts: Callable[[Sequence[Any]], dict[str, Any]]
    fits: Callable[[Sequence[float]], bool] = _always


def _sqrt(value: Any) -> Any:
    import sympy

    return sympy.sqrt(value)


FORMS: dict[str, Form] = {
    "window": Form(
        ("window",), (1.0, 1.4), lambda s: {"radius": s[0], "width": 2 * s[0], "height": s[1]}
    ),
    "rectangle": Form(("rectangle",), (3.0, 2.0), lambda s: {"width": s[0], "height": s[1]}),
    "square": Form(("square",), (2.0,), lambda s: {"side": s[0]}),
    "circle": Form(("circle",), (1.0,), lambda s: {"radius": s[0], "diameter": 2 * s[0]}),
    "cylinder": Form(
        ("cylinder",), (1.0, 2.2), lambda s: {"radius": s[0], "diameter": 2 * s[0], "height": s[1]}
    ),
    "cone": Form(
        ("cone",),
        (1.0, 2.0),
        lambda s: {
            "radius": s[0],
            "diameter": 2 * s[0],
            "height": s[1],
            "slant": _sqrt(s[0] ** 2 + s[1] ** 2),
        },
    ),
    "sphere": Form(("sphere",), (1.0,), lambda s: {"radius": s[0], "diameter": 2 * s[0]}),
    "frustum": Form(
        ("frustum",),
        (1.0, 2.0, 2.0),
        lambda s: {"top_radius": s[0], "bottom_radius": s[1], "height": s[2]},
        fits=lambda s: abs(s[0] - s[1]) > _TOLERANCE * max(s),
    ),
    # A square base when nothing sizes it: an open box's is, mostly, and a square is a
    # rectangle (round 3's c047, its computed sizes left off, drew a 3-by-2 base).
    "box": Form(
        ("box",),
        (3.0, 3.0, 1.8),
        lambda s: {"length": s[0], "width": s[1], "height": s[2]},
    ),
    # A sheet with a square cut from each corner, folded up into an open box.
    "sheet": Form(
        ("sheet",),
        (6.0, 4.0, 1.0),
        lambda s: {"length": s[0], "width": s[1], "cut": s[2]},
        fits=lambda s: 2 * s[2] < min(s[0], s[1]),
    ),
    "ladder": Form(
        ("ladder",),
        (1.0, 2.4),
        lambda s: {"length": _sqrt(s[0] ** 2 + s[1] ** 2), "foot": s[0], "top": s[1]},
    ),
    # A conical tank point down, the water's depth and the radius of its surface.
    "tank:cone": Form(
        ("cone",),
        (1.5, 3.0, 1.8),
        lambda s: {"radius": s[0], "height": s[1], "depth": s[2], "surface": s[0] * s[2] / s[1]},
        fits=lambda s: s[2] < s[1],
    ),
    "tank:cylinder": Form(
        ("cylinder",),
        (1.2, 3.0, 1.8),
        lambda s: {"radius": s[0], "height": s[1], "depth": s[2]},
        fits=lambda s: s[2] < s[1],
    ),
    # A cylinder standing inside a cone, its rim on the cone's side.
    "inscribed:cone": Form(
        ("cone", "cylinder"),
        (2.0, 3.0, 1.0),
        lambda s: {
            "outer_radius": s[0],
            "outer_height": s[1],
            "radius": s[2],
            "height": s[1] * (1 - s[2] / s[0]),
        },
        fits=lambda s: s[2] < s[0],
    ),
    # A cylinder inside a sphere, its rims on the sphere.
    "inscribed:sphere": Form(
        ("sphere", "cylinder"),
        (2.0, 1.2),
        lambda s: {
            "outer_radius": s[0],
            "radius": s[1],
            "height": 2 * _sqrt(s[0] ** 2 - s[1] ** 2),
        },
        fits=lambda s: s[1] < s[0],
    ),
}


# Each part's own word for the size beside its number: a stated size the question names as
# another part ("height 12 cm" on a radius) is not this part's.
PART_ROLES = {
    "radius": "radius", "top_radius": "radius", "bottom_radius": "radius",
    "outer_radius": "radius", "surface": "radius", "diameter": "diameter",
    "height": "height", "outer_height": "height", "top": "height", "depth": "depth",
    "width": "width", "length": "length", "side": "side", "slant": "slant",
}  # fmt: skip


def form_key(item: str, container: str | None) -> str:
    return f"{item}:{container}" if item in {"tank", "inscribed"} else item


@dataclass(frozen=True)
class Sized:
    """A shape's sizes and each part's label that holds on them."""

    sizes: tuple[float, ...]
    lengths: dict[str, float]
    shown: dict[str, str]


def _relations(
    lengths: dict[str, Any], labels: dict[str, Label]
) -> tuple[list[Any], list[tuple[str, str]]]:
    """What the labels' letters say: equations to impose (one letter on two parts, a
    multiple the question writes), and the pairs of parts whose ratio must already hold."""
    uses: dict[str, list[str]] = {}
    for part, label in labels.items():
        if label.letter is not None:
            uses.setdefault(label.letter, []).append(part)
    imposed: list[Any] = []
    implied: list[tuple[str, str]] = []
    for parts in uses.values():
        first = labels[parts[0]]
        for part in parts[1:]:
            label = labels[part]
            if label.coefficient == first.coefficient or label.written or first.written:
                relation = lengths[part] * first.coefficient - lengths[parts[0]] * label.coefficient
                imposed.append(relation)
            else:
                implied.append((parts[0], part))
    return imposed, implied


def _solved(symbols: Sequence[Any], equations: list[Any], start: list[float]) -> list[float] | None:
    """The sizes that meet every equation, the free ones taken from ``start`` in order; None
    when no positive sizes meet them, or more than one set does."""
    import sympy

    fixed: dict[Any, Any] = {}
    for _ in range(len(symbols) + 1):
        pending = [sympy.simplify(equation.subs(fixed)) for equation in equations]
        if any(item.is_number and abs(float(item)) > _TOLERANCE for item in pending):
            return None
        pending = [item for item in pending if not item.is_number]
        free = [symbol for symbol in symbols if symbol not in fixed]
        if not pending:
            values = [
                fixed.get(symbol, value) for symbol, value in zip(symbols, start, strict=True)
            ]
            return [float(value) for value in values]
        found = sympy.solve(pending, free, dict=True)
        if len(found) != 1:
            return None
        settled = {symbol: value for symbol, value in found[0].items() if value.is_number}
        if settled:
            fixed.update(settled)
            continue
        # A size the equations leave open takes its representative value.
        open_size = next(symbol for symbol in free if symbol not in found[0])
        fixed[open_size] = start[list(symbols).index(open_size)]
    return None


def _same_ratio(drawn: dict[str, float], pair: tuple[str, str], labels: dict[str, Label]) -> bool:
    (a, b) = pair
    mine, theirs = drawn[a] / float(labels[a].coefficient), drawn[b] / float(labels[b].coefficient)
    return abs(mine - theirs) <= 1e-6 * max(mine, theirs)


def _shown(
    labels: dict[str, Label], implied: list[tuple[str, str]], drawn: dict[str, float]
) -> dict[str, str]:
    """The labels that hold on the drawn shape. A multiple the question does not write
    stands only beside its letter's plain use, in the ratio the shape itself gives them."""
    wrong = {
        part
        for pair in implied
        if not _same_ratio(drawn, pair, labels)
        for part in pair
        if labels[part].coefficient != 1
    }
    letters = [label.letter for label in labels.values()]
    shown: dict[str, str] = {}
    for part, label in labels.items():
        alone = label.coefficient != 1 and not label.written and letters.count(label.letter) < 2
        if part not in wrong and not alone:
            shown[part] = label.text
    return shown


def sized(form: Form, labels: dict[str, Label]) -> Sized | None:
    """The shape drawn from ``labels``: its sizes, each part's length and the labels shown;
    None when its stated values cannot all hold, or hold in more than one way."""
    import sympy

    symbols = sympy.symbols(f"s0:{len(form.sizes)}", positive=True)
    lengths = form.parts(symbols)
    labels = {part: label for part, label in labels.items() if part in lengths}
    if len({label.unit for label in labels.values() if label.value is not None}) > 1:
        return None  # "2 m" and "50 cm" on one figure: no one scale draws both
    stated = [(part, label.value) for part, label in labels.items() if label.value is not None]
    equations = [lengths[part] - sympy.nsimplify(value) for part, value in stated]
    imposed, implied = _relations(lengths, labels)
    scale = 1.0
    if stated:
        part, value = stated[0]
        start = dict(zip(symbols, form.sizes, strict=True))
        scale = value / float(lengths[part].subs(start))
    sizes = _solved(symbols, equations + imposed, [size * scale for size in form.sizes])
    if sizes is None or not all(math.isfinite(s) and s > 0 for s in sizes) or not form.fits(sizes):
        return None
    at = dict(zip(symbols, sizes, strict=True))
    drawn = {part: float(length.subs(at)) for part, length in lengths.items()}
    return Sized(tuple(sizes), drawn, _shown(labels, implied, drawn))
