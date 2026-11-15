"""A ```draw description checked against the question and drawn, or nothing.

Runs in the SymPy pool (``drawn_fence`` is its picklable entry). The description is read
item by item (``vocabulary``), held to what the question states (``question``: its numbers,
points, letters and shape names), drawn by the server (a scene in space by ``scene`` and
``space``, a word problem's shapes by ``shapes`` and ``shape_drawings``), and the drawing
is checked last as every server figure is (``figure.honest``). A graph (kind "plot") is
checked and drawn by ``plot`` as a ```graph ``plot``. What fails is left out; a picture
whose main object fails is not drawn at all. A reply may carry one figure and one graph.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import Any

from app.modules.math.drawing.amounts import AMOUNTS, read_amount
from app.modules.math.drawing.labels import Label, read_length
from app.modules.math.drawing.plane import polygon_at
from app.modules.math.drawing.plot import plot_spec
from app.modules.math.drawing.question import Question, read_question
from app.modules.math.drawing.scene import checked_scene
from app.modules.math.drawing.shape_drawings import DRAWERS, beside, box
from app.modules.math.drawing.shapes import FORMS, PART_ROLES, Form, Sized, form_key, sized
from app.modules.math.drawing.space import draw_scene
from app.modules.math.drawing.vocabulary import ShapePart, read_description, read_items
from app.modules.math.figure.drawing import Drawing
from app.modules.math.figure.honest import honours, said
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.shape_names import names_shape
from app.modules.math.schemas.figure import FigureSpec

logger = logging.getLogger(__name__)

# At most this many shapes side by side in one word problem's figure.
_MOST_SHAPES = 3
# A reply's descriptions read, at most: one picture of each kind is drawn.
_MOST_DESCRIPTIONS = 3


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
        if label is not None and _its_part(name, label, question):
            labels[name] = label
    found = _sized(key, _drawn_as(form, labels), labels, part, question)
    if found is None:
        return None
    if part.item == "box":
        return box(found.sizes, found.shown, lid=not part.open)
    return DRAWERS[key](found.sizes, found.shown)


def _drawn_as(form: Form, labels: dict[str, Label]) -> Form:
    """The shape's representative proportions as its letters read: two radii lettered R and
    r are drawn with R the larger, whichever end the reply puts it at."""
    top, bottom = labels.get("top_radius"), labels.get("bottom_radius")
    if top is None or bottom is None or not top.letter or not bottom.letter:
        return form
    if top.letter.isupper() and bottom.letter == top.letter.lower():
        return replace(form, sizes=(form.sizes[1], form.sizes[0], *form.sizes[2:]))
    return form


def _sized(
    key: str, form: Form, labels: dict[str, Label], part: ShapePart, question: Question
) -> Sized | None:
    """The shape's sizes: from its labels, and from the amount the question fixes and the one
    it makes best, when the description names them (``amounts``)."""
    fixed: dict[str, tuple[float, str]] = {}
    for kind, text in part.fixed.items():
        amount = read_amount(kind, str(text), question)
        if amount is None:
            return None  # an amount the question does not state: no sizes worked from it
        fixed[kind] = amount
    goal = next(iter(part.optimise.items()), None)
    of = AMOUNTS.get(key)
    if (fixed or goal) and of is None:
        return None
    lid = not part.open
    amounts = (lambda symbols: of(symbols, lid)) if of is not None else None
    found = sized(form, labels, amounts=amounts, fixed=fixed, goal=goal)
    if found is None and goal is not None:
        # A best the description leaves unsettled (sizes left free): drawn without it.
        found = sized(form, labels, amounts=amounts, fixed=fixed)
    return found


def _its_part(part: str, label: Label, question: Question) -> bool:
    """A stated size the question names beside its number ("radius 5 cm", "12 m long") goes
    on that part only: a cone's 12 cm height is never its radius."""
    if label.value is None:
        return True
    roles = question.roles(label.value)
    return not roles or PART_ROLES.get(part) in roles


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
    """A label's stated value and unit ("12 m" and "r = 12 m": 12 and "m"), or None for a
    letter ("r", "h = 3r")."""
    head, _, unit = said(label).partition(" ")
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
    items = read_items(description)
    kind = description.kind
    if kind == "plot":
        return _graph_fence(items, texts, reply)
    question = read_question(texts, reply)
    try:
        if kind == "space":
            scene = checked_scene(items, question)
            spec = draw_scene(scene) if scene is not None else None
        else:
            spec = _shapes(items, question)
    except Exception:  # SymPy's own errors included: a description that fails draws nothing.
        logger.info("drawing failed for a %s picture", kind, exc_info=True)
        return None
    if spec is None or not _held(spec):
        return None
    body_out = {"type": spec.type, **spec.model_dump(exclude_defaults=True)}
    return f"```geometry\n{json.dumps(body_out, separators=(',', ':'), ensure_ascii=False)}\n```"


def _graph_fence(items: list[tuple[str, Any | None]], texts: list[str], reply: str) -> str | None:
    try:
        spec = plot_spec(items, texts, reply)
    except Exception:  # SymPy's and numpy's own errors included: it draws nothing.
        logger.info("drawing failed for a plot picture", exc_info=True)
        return None
    if spec is None:
        return None
    return (
        f"```graph\n{json.dumps(spec.model_dump(), separators=(',', ':'), ensure_ascii=False)}\n```"
    )


def drawn_fences(bodies: list[str], texts: list[str], reply: str) -> list[str]:
    """Picklable entry for ``core.sympy_executor.run_sympy``: the pictures the descriptions
    draw, one of each kind (a ```geometry figure, a ```graph), each from the first
    description of that kind that checks (owner decision 2026-11-15: a reply may carry a
    figure and a graph)."""
    drawn: dict[str, str] = {}
    for body in bodies[:_MOST_DESCRIPTIONS]:
        fence = drawn_fence(body, texts, reply)
        kind = fence.split("\n", 1)[0].removeprefix("```") if fence else ""
        if fence is not None and kind not in drawn:
            drawn[kind] = fence
    return list(drawn.values())
