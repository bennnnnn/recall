"""The region three curves or lines enclose, a curved triangle.

Each pair of edges meets once at a corner the server finds; the corners in order along x
cut the region in two, each part lying between the two edges that meet at its outer corner.
It is drawn only when that holds: the edge the two parts share stays on one side of both
others, so the parts close up into one region. Otherwise nothing is shaded.
"""

from __future__ import annotations

from itertools import combinations, product
from typing import Any

import numpy as np
from sympy import Float

from app.modules.math.drawing.curve_features import snapped, zeros
from app.modules.math.drawing.plot_check import edge_function
from app.modules.math.drawing.plot_items import Shade
from app.modules.math.drawing.plot_labels import point_text
from app.modules.math.drawing.plot_scene import DrawnPoint, DrawnRegion, Scene, Shaded
from app.modules.math.drawing.real_curve import RealFunction

_SAMPLES = 120
_MOST_CORNERS = 3


def _part(
    one: RealFunction, two: RealFunction, a: float, b: float
) -> list[tuple[float, float]] | None:
    ts = np.linspace(a, b, _SAMPLES)
    upper, lower = one.values(ts), two.values(ts)
    if not (np.all(np.isfinite(upper)) and np.all(np.isfinite(lower))):
        return None
    return [
        (float(t), float(v))
        for t, v in [*zip(ts, upper, strict=True), *zip(ts[::-1], lower[::-1], strict=True)]
    ]


def _side(top: RealFunction, other: RealFunction, a: float, b: float) -> float:
    middle = (a + b) / 2
    return float(np.sign(top.at(middle) - other.at(middle)))


def enclosed(item: Shade, scene: Scene) -> None:
    edges = [edge_function(name, scene) for name in item.between]
    if any(edge is None for edge in edges) or item.wrt != "x":
        return
    fns: list[RealFunction] = [edge for edge in edges if edge is not None]
    reach = max(abs(v) for curve in scene.curves.values() for v in curve.search)
    meets: dict[tuple[int, int], list[float]] = {}
    for i, j in combinations(range(3), 2):
        found = zeros(RealFunction(fns[i].expr - fns[j].expr).values, -reach, reach)
        if not found:
            return
        meets[(i, j)] = found[:_MOST_CORNERS]
    for corners in product(*meets.values()):
        drawn = _drawn(fns, list(zip(meets.keys(), corners, strict=True)))
        if drawn is None:
            continue
        parts, placed = drawn
        for part in parts:
            scene.regions.append(DrawnRegion(part))
        for (i, j), x in placed:
            exact = snapped(x, [], fns[i].expr - fns[j].expr)
            y = fns[i].exact_at(exact) if not exact.is_Float else None
            y = y if y is not None else Float(fns[i].at(x), 12)
            scene.add_point(DrawnPoint(float(exact), float(y), point_text(exact, y)))
        low, high = min(c for _, c in placed), max(c for _, c in placed)
        scene.shaded.append(Shaded(fns[0], fns[1], low, high, "x"))
        return


def _drawn(fns: list[RealFunction], corners: list[tuple[tuple[int, int], float]]) -> Any:
    ordered = sorted(corners, key=lambda c: c[1])
    (left_pair, a), (_, m), (right_pair, b) = ordered
    if not a < m < b:
        return None
    shared = set(left_pair) & set(right_pair)
    if len(shared) != 1:
        return None
    k = shared.pop()
    left_other = (set(left_pair) - {k}).pop()
    right_other = (set(right_pair) - {k}).pop()
    side = _side(fns[k], fns[left_other], a, m)
    if side == 0 or side != _side(fns[k], fns[right_other], m, b):
        return None
    first = _part(fns[k], fns[left_other], a, m)
    second = _part(fns[k], fns[right_other], m, b)
    if first is None or second is None:
        return None
    return [first, second], ordered
