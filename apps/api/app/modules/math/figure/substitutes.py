"""Where a drawn picture meets the reply: whether the server's pictures already show it, and
the model's own picture of it in rows of characters taken out once it comes.

A solve's own picture is the whole picture when it is a graph, a scene or a teaching
picture. A plane shape it drew may be only a part of what the question asks to see: the
textbook's "right triangular prism whose base is a right-angled triangle with sides 6, 8
and 10" drew the base triangle and no prism (2026-11-13). So a solid or its net, and a
circle with a chord or a shape inside or around it, join a reply whose only pictures are
plane shapes; any other picture the reply already holds stands alone.
"""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Any

from app.modules.math.text_plot import strip_text_plots
from app.services.md_fence_scan import has_closed_fence, iter_closed_fences, strip_closed_fences
from app.services.solving import VerifiedMathBlock

# The fences a picture the server drew comes in: maths' figures and graphs, physics' scenes.
_PICTURE_FENCES = ("geometry", "graph", "simulation")
# Points of a function graph checked on a drawn curve before it counts as that curve.
_COMPARED = 5
# A solve's pictures that are the whole picture: a graph or a teaching picture.
_WHOLE_KINDS = frozenset({"graph", "teach"})
# The solids a figure draws, and their nets: a plane shape is at most one of their parts.
_SOLIDS = frozenset(
    {
        "cube",
        "cuboid",
        "triangular_prism",
        "square_pyramid",
        "cylinder",
        "cone",
        "sphere",
        "hemisphere",
    }
)


def verified_picture(verified: Any) -> bool:
    """The turn's verified block draws the whole picture: a graph or a teaching picture, or
    a peer subject's own (physics' scene, chemistry's molecule)."""
    if verified is None:
        return False
    if not isinstance(verified, VerifiedMathBlock):
        return True
    from app.modules.math.fence import collect_canonical_specs, spec_fence_kind

    return any(spec_fence_kind(spec) in _WHOLE_KINDS for spec in collect_canonical_specs(verified))


def holds_whole_picture(text: str) -> bool:
    """The reply already holds a picture no figure adds to: a graph or a scene."""
    return has_closed_fence(text, "graph") or has_closed_fence(text, "simulation")


def _draws_more_than_one_shape(fence: str) -> bool:
    """A solid or its net, or a circle with a chord or a shape inside or around it: a
    picture a plane shape the solve drew is only a part of."""
    try:
        body = json.loads(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])
    except (IndexError, json.JSONDecodeError):
        return False
    shape = str(body.get("shape", "")) if isinstance(body, dict) else ""
    return shape.removesuffix("_net") in _SOLIDS or (
        shape.startswith("circle_") and shape != "circle_parts"
    )


def adds_to(text: str, fence: str) -> bool:
    """``fence`` shows what the reply's own pictures do not: the reply holds none, or only
    plane shapes that are parts of the figure it draws."""
    if not any(has_closed_fence(text, lang) for lang in _PICTURE_FENCES):
        return True
    if holds_whole_picture(text) or not _draws_more_than_one_shape(fence):
        return False
    return all(
        '"type":"figure"' not in "".join(body.split())
        for _start, _end, body in iter_closed_fences(text, "geometry")
    )


def without_substitutes(text: str) -> str:
    """The prompt asks for no picture in characters (``GRAPH_NO_SUBSTITUTE_CLAUSE``); a reply
    that still drew its number line or graph in characters loses it beside the real one. A
    Mermaid diagram is never taken out: "show the steps as a flow diagram" asked for one."""
    return strip_text_plots(text)


def without_drawn_substitutes(text: str) -> str:
    """The reply described its picture (a ```draw block the server drew, in ``text`` now):
    anything else it drew for that picture stands in for it. A Mermaid flowchart standing in
    for two vectors (round 3, c082) goes, with a sketch in characters, and a function graph
    of a curve the checked graph draws (c009 showed both); a flow diagram a question asks for
    gets no ```draw block, and keeps its Mermaid. A solver's number line, an inequality's
    region, a graph of points or of another curve stays."""
    return _without_replaced_graphs(strip_closed_fences(strip_text_plots(text), "mermaid"))


def _graph_body(body: str) -> dict[str, Any] | None:
    try:
        spec = json.loads(body)
    except ValueError:
        return None
    return spec if isinstance(spec, dict) else None


def _drawn_segments(text: str) -> list[list[list[tuple[float, float]]]]:
    """Each curve of the checked graphs (```graph ``plot``) in ``text``, as its segments."""
    found: list[list[list[tuple[float, float]]]] = []
    for _start, _end, body in iter_closed_fences(text, "graph"):
        spec = _graph_body(body)
        if spec is None or spec.get("type") != "plot":
            continue
        for curve in spec.get("curves") or []:
            found.append([[(float(x), float(y)) for x, y in seg] for seg in curve["segments"]])
    return found


def _on_curve(points: list[Any], segments: list[list[tuple[float, float]]]) -> bool:
    """Every point of ``points`` that a segment spans lies on it (between the samples beside
    it, give or take a fiftieth of the curve's height), and enough of them to tell."""
    ys = [y for seg in segments for _x, y in seg]
    if not ys:
        return False
    slack = 0.02 * (max(ys) - min(ys) + 1e-9)
    compared = 0
    for point in points[:: max(1, len(points) // 40)]:
        x, y = float(point[0]), float(point[1])
        for seg in segments:
            beside = next(((a, b) for a, b in pairwise(seg) if a[0] <= x <= b[0]), None)
            if beside is None or not min(ys) <= y <= max(ys):
                continue
            low, high = sorted((beside[0][1], beside[1][1]))
            if not low - slack <= y <= high + slack:
                return False
            compared += 1
            break
    return compared >= _COMPARED


def _replaced(spec: dict[str, Any], drawn: list[list[list[tuple[float, float]]]]) -> bool:
    """A function graph each of whose curves the checked graph draws."""
    if spec.get("type", "function") != "function":
        return False
    # Its points, as the maths fence pass sampled them before the picture comes.
    curves = [points for key in ("points", "points2") if (points := spec.get(key))]
    return bool(curves) and all(
        any(_on_curve(points, segments) for segments in drawn) for points in curves
    )


def _without_replaced_graphs(text: str) -> str:
    drawn = _drawn_segments(text)
    if not drawn:
        return text
    pieces: list[str] = []
    cursor = 0
    for start, end, body in iter_closed_fences(text, "graph"):
        spec = _graph_body(body)
        if spec is not None and _replaced(spec, drawn):
            pieces.append(text[cursor:start])
            cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)
