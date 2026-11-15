"""A reading of what to draw, made into the fence the phone draws, or nothing.

Runs in the SymPy pool (``build_figure_fence`` is its picklable entry): the numbers are
checked against the question first (``grounding``), then the kind's builder draws it, and
the drawing is checked against the question last (``honest``). A builder that cannot meet
what the question states returns None, and so does this.
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.modules.math.figure import circles, coordinate, lines, nets, solids
from app.modules.math.figure.grounding import grounded, own_texts, with_unit, written_pairs
from app.modules.math.figure.honest import honours
from app.modules.math.figure.polygon import build_polygon
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.shape_names import names_shape
from app.modules.math.schemas.figure import FigureSpec
from app.services.solving import SolveServiceError

logger = logging.getLogger(__name__)


def _figure(request: FigureRequest) -> FigureSpec | None:
    if request.kind == "polygon":
        return build_polygon(request)
    if request.kind == "circle":
        return circles.build_circle(request)
    if request.kind == "lines":
        return lines.build_lines(request)
    if request.kind == "solid":
        return nets.build_net(request) if request.has_part("net") else solids.build_solid(request)
    return None


def _fence(lang: str, body: dict[str, object]) -> str:
    return f"```{lang}\n{json.dumps(body, separators=(',', ':'), ensure_ascii=False)}\n```"


# A solid or a circle is drawn only for a question that names it, and never for one that
# names it as part of another shape: round 3 (2026-11-14) drew a cone for a frustum.
_NAMED = {
    "cone": "cone",
    "cylinder": "cylinder",
    "sphere": "sphere",
    "hemisphere": "hemisphere",
    "cube": "closed_box",
    "cuboid": "closed_box",
}


def _the_questions_shape(request: FigureRequest, texts: list[str]) -> bool:
    """The reading's shape is the one the question names, where it is: not a default in
    its place. A polygon whose corners the question gives as coordinates is drawn there or
    not at all; a triangle drawn to a default size in their place was wrong (round 3)."""
    if request.kind == "circle":
        return names_shape(texts, "circle")
    if request.kind == "solid" and request.shape in _NAMED:
        return names_shape(texts, _NAMED[request.shape])
    if request.kind == "polygon":
        return len({pair for text in own_texts(texts) for pair in written_pairs(text)}) < 3
    return True


def figure_fence(request: FigureRequest, texts: list[str]) -> str | None:
    """The picture's fence (```geometry or ```graph), or None when nothing is drawn."""
    request = with_unit(request, texts)
    if request.kind == "none" or not grounded(request, texts):
        return None
    if not _the_questions_shape(request, texts):
        return None
    if request.kind in {"number_line", "points"} and coordinate.writes_a_formula(own_texts(texts)):
        return None  # the formula beside them would be left out
    try:
        if request.kind == "number_line":
            line = coordinate.number_line(request, texts)
            return None if line is None else _fence("graph", line)
        if request.kind == "function":
            graph = coordinate.function_graph(request, texts)
            return None if graph is None else _fence("graph", graph)
        if request.kind == "points":
            points = coordinate.points_graph(request)
            return None if points is None else _fence("graph", points)
        spec = _figure(request)
    except (SolveServiceError, ValidationError, ValueError, ZeroDivisionError):
        logger.info("figure build failed for %s %s", request.kind, request.shape, exc_info=True)
        return None
    if spec is None or not honours(spec, request):
        return None
    # Defaults left out keep the fence small; its type stays, as the phone reads it first.
    return _fence("geometry", {"type": spec.type, **spec.model_dump(exclude_defaults=True)})


def build_figure_fence(request_json: str, texts: list[str]) -> str | None:
    """Picklable entry for ``core.sympy_executor.run_sympy``."""
    try:
        request = FigureRequest.model_validate_json(request_json)
    except ValidationError:
        return None
    return figure_fence(request, texts)
