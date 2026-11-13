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
from app.modules.math.figure.grounding import grounded, with_unit
from app.modules.math.figure.honest import honours
from app.modules.math.figure.polygon import build_polygon
from app.modules.math.figure.request import FigureRequest
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


def figure_fence(request: FigureRequest, texts: list[str]) -> str | None:
    """The picture's fence (```geometry or ```graph), or None when nothing is drawn."""
    request = with_unit(request, texts)
    if request.kind == "none" or not grounded(request, texts):
        return None
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
