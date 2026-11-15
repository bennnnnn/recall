"""A ```draw description checked against the question and drawn, or nothing.

Runs in the SymPy pool (``drawn_fence`` is its picklable entry). The description is read
item by item (``vocabulary``), held to what the question states (``question``: its numbers,
points, letters and shape names), drawn by the server (a scene in space by ``scene`` and
``space``, a word problem's shapes by ``shapes`` and ``shape_drawings``), and the drawing
is checked last as every server figure is (``figure.honest``). What fails is left out; a
picture whose main object fails is not drawn at all.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.modules.math.drawing.labels import Label, read_length
from app.modules.math.drawing.plane import polygon_at
from app.modules.math.drawing.question import Question, read_question
from app.modules.math.drawing.scene import checked_scene
from app.modules.math.drawing.shape_drawings import DRAWERS, beside, box
from app.modules.math.drawing.shapes import FORMS, form_key, sized
from app.modules.math.drawing.space import draw_scene
from app.modules.math.drawing.vocabulary import ShapePart, read_description, read_items
from app.modules.math.figure.drawing import Drawing
from app.modules.math.figure.honest import honours
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.shape_names import names_shape
from app.modules.math.schemas.figure import FigureSpec
from app.services.solving import SolveServiceError

logger = logging.getLogger(__name__)

# At most this many shapes side by side in one word problem's figure.
_MOST_SHAPES = 3
# A reply's descriptions read, at most: one picture is drawn, from the first that checks.
_MOST_DESCRIPTIONS = 2


def _shape(part: ShapePart, question: Question) -> Drawing | None:
    """One shape of a word problem's figure, or None when it is not the question's."""
    if part.item == "polygon":
        return polygon_at(part, question)
    key = form_key(part.item, part.container)
    form = FORMS.get(key)
    if form is None or not all(names_shape([question.words], name) for name in form.named):
        return None
    labels: dict[str, Label] = {}
    for name, text in part.labels().items():
        label = read_length(text, question)
        if label is not None:
            labels[name] = label
    found = sized(form, labels)
    if found is None:
        return None
    if part.item == "box":
        return box(found.sizes, found.shown, lid=not part.open)
    return DRAWERS[key](found.sizes, found.shown)


def _shapes(items: list[tuple[str, Any | None]], question: Question) -> FigureSpec | None:
    """Every shape is the figure's: one that fails takes the figure with it."""
    if not 0 < len(items) <= _MOST_SHAPES:
        return None
    drawings: list[Drawing] = []
    for _name, part in items:
        drawing = _shape(part, question) if isinstance(part, ShapePart) else None
        if drawing is None:
            return None
        drawings.append(drawing)
    if len(drawings) > 1 and any(d.shape == "polygon" for d in drawings):
        return None  # a polygon on its axes stands alone
    shape = drawings[0].shape if len(drawings) == 1 else "shapes"
    return beside(drawings, shape).spec()


def _held(spec: FigureSpec) -> bool:
    """``figure.honest``'s last check: every stated value it labels is true where it sits; a
    letter names a part and is not measured. One figure is drawn in one unit."""
    labels = [
        label
        for label in [*(s.label for s in spec.segments), *(a.label for a in spec.angles)]
        if label
    ]
    measures: list[Measure] = []
    units: set[str] = set()
    letters: set[str] = set()
    for label in labels:
        value, unit = _value(label)
        if value is None:
            letters.add(label)
        elif label.endswith("°"):
            measures.append(Measure(what="angle", value=value))
        else:
            measures.append(Measure(what="length", value=value))
            units.add(unit)
    if len(units) > 1:
        return False
    request = FigureRequest(
        kind="polygon", shape=spec.shape, measures=measures, unit=next(iter(units), "")
    )
    return honours(spec, request, letters=frozenset(letters))


def _value(label: str) -> tuple[float | None, str]:
    """A label's stated value and unit ("12 m": 12 and "m"), or None for a letter."""
    head, _, unit = label.partition(" ")
    try:
        return float(head.rstrip("°")), unit
    except ValueError:
        return None, ""


def drawn_fence(body: str, texts: list[str], reply: str) -> str | None:
    """The checked picture's ```geometry fence, or None. ``texts``: the last user message
    first, then earlier ones; ``reply``: the reply's text, whose working names its letters."""
    description = read_description(body)
    if description is None:
        return None
    question = read_question(texts, reply)
    items = read_items(description)
    try:
        if description.kind == "space":
            scene = checked_scene(items, question)
            spec = draw_scene(scene) if scene is not None else None
        else:
            spec = _shapes(items, question)
    except (SolveServiceError, ValidationError, ValueError, ZeroDivisionError, TypeError):
        logger.info("drawing failed for a %s description", description.kind, exc_info=True)
        return None
    if spec is None or not _held(spec):
        return None
    body_out = {"type": spec.type, **spec.model_dump(exclude_defaults=True)}
    return f"```geometry\n{json.dumps(body_out, separators=(',', ':'), ensure_ascii=False)}\n```"


def first_drawn_fence(bodies: list[str], texts: list[str], reply: str) -> str | None:
    """Picklable entry for ``core.sympy_executor.run_sympy``: the first description that
    checks, drawn. A turn shows one such picture."""
    for body in bodies[:_MOST_DESCRIPTIONS]:
        fence = drawn_fence(body, texts, reply)
        if fence is not None:
            return fence
    return None
