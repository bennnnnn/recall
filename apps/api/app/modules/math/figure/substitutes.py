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
from typing import Any

from app.modules.math.text_plot import strip_text_plots
from app.services.md_fence_scan import has_closed_fence, iter_closed_fences
from app.services.solving import VerifiedMathBlock

# The fences a picture the server drew comes in: maths' figures and graphs, physics' scenes.
_PICTURE_FENCES = ("geometry", "graph", "simulation")
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
