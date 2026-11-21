"""A reading of what to draw, made into the fence the phone draws, or nothing.

Runs in the SymPy pool (``build_figure_fence`` is its picklable entry): the numbers are
checked against the question first (``grounding``), then the kind's builder draws it, and
the drawing is checked against the question last (``honest``). A builder that cannot meet
what the question states returns None, and so does this.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence

from pydantic import ValidationError

from app.modules.math.drawing.plot_question import read_plot_question
from app.modules.math.figure import (
    circles,
    composite,
    coordinate,
    cut_cones,
    frustums,
    heights,
    inscribed_solids,
    lines,
    nets,
    plane,
    quads,
    right_altitude,
    solids,
    stacked_solids,
    two_circles,
)
from app.modules.math.figure.angle_terms import term_labels, terms_written
from app.modules.math.figure.grounding import grounded, own_texts, with_unit, written_pairs
from app.modules.math.figure.honest import honours
from app.modules.math.figure.polygon import build_polygon, read_whole
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.revolution import revolves_into
from app.modules.math.figure.shape_names import names_shape
from app.modules.math.reading import student_reading
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
        return _solid(request)
    return None


def _solid(request: FigureRequest) -> FigureSpec | None:
    shape = request.shape
    if inscribed_solids.holds_sphere(request):
        return inscribed_solids.build_inscribed(request)
    if request.attached:
        return stacked_solids.build_stacked(request)
    if shape in frustums.FRUSTUMS:
        cut = cut_cones.is_cut(request)
        return cut_cones.build_cut_cone(request) if cut else frustums.build_frustum(request)
    if shape in frustums.PYRAMID_FRUSTUMS:
        return frustums.build_pyramid_frustum(request)
    if shape in frustums.TETRAHEDRA:
        return frustums.build_tetrahedron(request)
    return nets.build_net(request) if request.has_part("net") else solids.build_solid(request)


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
    "frustum": "frustum",
}


def _the_questions_shape(request: FigureRequest, texts: list[str]) -> bool:
    """The reading's shape is the one the question names, where it is: not a default in
    its place. A polygon whose corners the question gives as coordinates is drawn there or
    not at all; a triangle drawn to a default size in their place was wrong (round 3)."""
    if request.attached and not _names_attached(request, texts):
        return False
    if request.kind == "circle":
        return names_shape(texts, "circle")
    if request.kind == "solid" and not revolves_into(request.shape, texts):
        return False  # x = √y about the y-axis is no cylinder (u5-083)
    if request.kind == "solid" and request.shape in _NAMED:
        return names_shape(texts, _NAMED[request.shape])
    if request.kind == "polygon":
        return len({pair for text in own_texts(texts) for pair in written_pairs(text)}) < 3
    return True


def _names_attached(request: FigureRequest, texts: list[str]) -> bool:
    """A shape made of two is one the question names both parts of: a semicircle, a
    triangle or a second rectangle it writes, a cone or a hemisphere it names."""
    if request.kind == "polygon":
        # A second shape no composite draws ("shadows") is drawn by its own builder or not.
        attached = request.attached
        return attached not in composite.ATTACHED or composite.names_part(texts, attached)
    solid = request.attached.removeprefix("two_").removesuffix("s")
    return (
        solid in _NAMED
        and names_shape(texts, _NAMED[solid])
        and any(solid[:5] in text.lower() for text in texts)
    )


# The readings held to words that always leave one standing: a right triangle's altitude
# onto its hypotenuse, an isosceles trapezium read as any, a sphere inside a solid, which
# cone of a cut one a value is of, whether two circles touch.
_SAID: tuple[Callable[[FigureRequest, Sequence[str]], FigureRequest], ...] = (
    right_altitude.as_said,
    quads.trapezium_as_said,
    inscribed_solids.as_said,
    cut_cones.roles_as_said,
    two_circles.as_said,
)


def _as_said(request: FigureRequest, texts: list[str]) -> FigureRequest | None:
    """The reading held to the question's words where a builder alone cannot tell: the side
    a shape made of two stands on, the side a scene's two points are on, those of ``_SAID``,
    what a solid made of two gives a height of."""
    said = composite.side_as_said(request, texts)
    said = None if said is None else heights.as_said(said, texts)
    if said is None:
        return None
    for read in _SAID:
        said = read(said, texts)
    return stacked_solids.heights_as_said(said, texts)


def _plane_fence(request: FigureRequest, texts: list[str]) -> str | None:
    """Coordinate geometry and transformations, drawn where the question puts them."""
    try:
        graph = plane.plane_graph(request, texts)
    except (SolveServiceError, ValidationError, ValueError, ZeroDivisionError):
        logger.info("plane figure build failed", exc_info=True)
        return None
    return None if graph is None else _fence("graph", graph)


def figure_fence(request: FigureRequest, texts: list[str]) -> str | None:
    """The picture's fence (```geometry or ```graph), or None when nothing is drawn."""
    request = with_unit(request, texts)
    if request.kind == "polygon":
        request = read_whole(request)
    x_values = read_plot_question(texts).x_values if request.bounds() != (None, None) else ()
    if request.kind == "none" or not grounded(request, texts, x_values):
        return None
    if not terms_written(request, own_texts(texts)):
        return None
    if plane.is_plane(request, texts):
        return _plane_fence(request, texts)
    if not _the_questions_shape(request, texts):
        return None
    said = _as_said(request, own_texts(texts))
    if said is None:
        return None
    request = said
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
    if spec is None or not honours(spec, request, letters=term_labels(request)):
        return None
    # Defaults left out keep the fence small; its type stays, as the phone reads it first.
    return _fence("geometry", {"type": spec.type, **spec.model_dump(exclude_defaults=True)})


# A question pasted as LaTeX (a worksheet's "\\(6\\text{ cm}\\)", "\\(45^{\\circ}\\)").
_LATEX = re.compile(r"\\[()\[\]]|\\[A-Za-z]+|\^\s*\{")


def as_written(text: str) -> str:
    """The question as a student reads it: LaTeX pasted from a worksheet becomes its plain
    text ("6 cm", "45°"), so its numbers are found with their units. Read raw, "45^{\\circ}"
    was a power and "6\\text{ cm}" had no unit, and no figure was drawn for any of three
    pasted questions (2026-11-20). Plain text is left as it is."""
    return student_reading(text) if _LATEX.search(text) else text


def build_figure_fence(request_json: str, texts: list[str]) -> str | None:
    """Picklable entry for ``core.sympy_executor.run_sympy``."""
    try:
        request = FigureRequest.model_validate_json(request_json)
    except ValidationError:
        return None
    return figure_fence(request, [as_written(text) for text in texts])
