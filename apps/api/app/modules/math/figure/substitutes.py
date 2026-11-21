"""Where a drawn picture meets the reply: whether the server's pictures already show it, and
the model's own picture of it in rows of characters taken out once it comes.

A solve's own picture is the whole picture when it is a graph, a scene or a teaching
picture. A plane shape it drew (a circle, a rectangle, a triangle by its sides) is at most a
part of what the question asks to see: the textbook's "right triangular prism whose base is a
right-angled triangle with sides 6, 8 and 10" drew the base triangle and no prism
(2026-11-13), and a chord's question drew a bare circle (2026-11-21). So a figure takes the
place of the solve's plain shape: one geometry picture a turn, labelled with the question's
own values. A solid or its net, and a circle with a chord or a shape inside or around it,
also join a reply whose other pictures are the model's plane shapes; any other picture the
reply already holds stands alone.
"""

from __future__ import annotations

import json
import re
from itertools import pairwise
from typing import Any

from app.modules.math.text_plot import strip_text_plots
from app.services.md_fence_scan import has_closed_fence, iter_closed_fences, strip_closed_fences
from app.services.sketches import asks_for_a_diagram
from app.services.solving import VerifiedMathBlock

# The fences a picture the server drew comes in: maths' figures and graphs, physics' scenes.
_PICTURE_FENCES = ("geometry", "graph", "simulation")
# A solve's plain shape pictures (``schemas/geometry``), each one shape at its measures.
SOLVER_SHAPES = frozenset(
    {"triangle", "right_triangle", "triangle_sides", "trapezoid", "parallelogram", "sector",
     "circle", "rectangle", "rect", "square"}
)  # fmt: skip
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
    plane shapes that are parts of the figure it draws. A solve's plain shape never stands
    in a figure's way: the figure takes its place (``without_substitutes``)."""
    if _is_figure(fence):
        text = _without_solver_shapes(text)
    if not any(has_closed_fence(text, lang) for lang in _PICTURE_FENCES):
        return True
    if holds_whole_picture(text) or not _draws_more_than_one_shape(fence):
        return False
    return all(
        '"type":"figure"' not in "".join(body.split())
        for _start, _end, body in iter_closed_fences(text, "geometry")
    )


def without_substitutes(text: str, fence: str) -> str:
    """The pictures ``fence`` stands in for, taken out of the reply. The prompt asks for no
    picture in characters (``GRAPH_NO_SUBSTITUTE_CLAUSE``); a reply that still drew its number
    line or graph in characters loses it beside the real one. A Mermaid diagram is never
    taken out: "show the steps as a flow diagram" asked for one.

    A figure is the turn's one picture of its shape: the solve's plain shape of the same
    question goes. A bare circle stood beside the chord's figure, and a 13-14-15 triangle
    labelled with its worked angles and area beside the question's own values (2026-11-21);
    a figure labels only the question's values."""
    text = strip_text_plots(text)
    return _without_solver_shapes(text) if _is_figure(fence) else text


def _fence_type(body: str) -> str | None:
    try:
        spec = json.loads(body)
    except ValueError:
        return None
    kind = spec.get("type") if isinstance(spec, dict) else None
    return kind if isinstance(kind, str) else None


def _is_figure(fence: str) -> bool:
    """``fence`` is a figure the server drew (```geometry of type "figure")."""
    lang, _newline, rest = fence.partition("\n")
    return lang.strip() == "```geometry" and _fence_type(rest.rsplit("```", 1)[0]) == "figure"


def _without_solver_shapes(text: str) -> str:
    """``text`` without a solve's plain shape (a circle, a rectangle, a triangle by its sides)."""
    pieces: list[str] = []
    cursor = 0
    for start, end, body in iter_closed_fences(text, "geometry"):
        if _fence_type(body) in SOLVER_SHAPES:
            pieces.append(text[cursor:start])
            cursor = end
    pieces.append(text[cursor:])
    return re.sub(r"\n{3,}", "\n\n", "".join(pieces)) if cursor else text


def without_drawn_substitutes(text: str, user_text: str = "") -> str:
    """The reply described its picture (a ```draw block the server drew, in ``text`` now):
    anything else it drew for that picture stands in for it. A Mermaid flowchart standing in
    for two vectors (round 3, c082) goes, with a sketch in characters, and a function graph
    of a curve the checked graph draws (c009 showed both); a flow diagram a question asks for
    gets no ```draw block, and keeps its Mermaid, and so does one ``user_text`` asks for
    beside the picture. A solver's number line, an inequality's region, a graph of points or
    of another curve stays."""
    text = strip_text_plots(text)
    if not asks_for_a_diagram(user_text):
        text = strip_closed_fences(text, "mermaid")
    return _without_replaced_graphs(text)


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
