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
import re
from dataclasses import replace
from typing import Any

from app.modules.math.drawing.amounts import AMOUNTS, read_amount
from app.modules.math.drawing.labels import Label, read_length
from app.modules.math.drawing.plane import polygon_at
from app.modules.math.drawing.question import Question, read_question
from app.modules.math.drawing.roles import PART_ROLES, stated_on
from app.modules.math.drawing.scene import checked_scene
from app.modules.math.drawing.shape_drawings import DRAWERS, beside, box
from app.modules.math.drawing.shapes import FORMS, Form, Sized, form_key, sized
from app.modules.math.drawing.space import draw_scene
from app.modules.math.drawing.vocabulary import ShapePart, read_description, read_items
from app.modules.math.figure.drawing import Drawing
from app.modules.math.figure.honest import honours, said
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.shape_names import lid_said, names_shape
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
    roles = [PART_ROLES.get(name, name) for name in form.parts(form.sizes)]
    for name, text in part.labels().items():
        label = read_length(text, question)
        if label is not None and _its_part(name, label, roles, question):
            labels[name] = label
    said = lid_said(question.texts)
    lid = not part.open if said is None else said
    # A lid the description and the question disagree on, or one the question says both of,
    # leaves the amounts unworked: a closed can's best size is not an open one's.
    trusted = said is not None and said == (not part.open)
    found = _sized(key, _drawn_as(form, labels), labels, part, question, lid, trusted)
    if found is None:
        return None
    if part.item == "box":
        return box(found.sizes, found.shown, lid=lid)
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


# The words that make a box's base square, and all its edges one.
_SQUARE_BASE = re.compile(r"\bsquare(?:[- ]based|\s+(?:base|bottom|end|ends))\b")
_CUBE = re.compile(r"\bcub(?:e|es|ic|ical)\b(?!\s+(?:units?|cm|m|metres?|feet|inch))")


def _equal(key: str, question: Question) -> frozenset[frozenset[str]]:
    """The parts the question makes equal: a square base's length and width, a cube's edges."""
    if key != "box":
        return frozenset()
    if _CUBE.search(question.words):
        return frozenset(
            {frozenset({"length", "width"}), frozenset({"length", "height"}),
             frozenset({"width", "height"})}
        )  # fmt: skip
    if _SQUARE_BASE.search(question.words):
        return frozenset({frozenset({"length", "width"})})
    return frozenset()


def _sized(
    key: str,
    form: Form,
    labels: dict[str, Label],
    part: ShapePart,
    question: Question,
    lid: bool,
    trusted: bool,
) -> Sized | None:
    """The shape's sizes: from its labels, and from the amount the question fixes and the one
    it makes best, when the description names them (``amounts``). A size worked from them is
    shown only where the lid is the question's and the reply works it out to the same value;
    else the shape is drawn in its representative proportion, its letters bare."""
    equal = _equal(key, question)
    plain = sized(form, labels, equal=equal)
    if not part.fixed and not part.optimise:
        return plain
    if not trusted and "surface" in {*part.fixed, *part.optimise}:
        return plain
    fixed: dict[str, tuple[float, str]] = {}
    for kind, text in part.fixed.items():
        amount = read_amount(kind, str(text), question)
        if amount is None:
            return plain  # an amount the question does not state: no sizes worked from it
        fixed[kind] = amount
    goal = next(iter(part.optimise.items()), None)
    of = AMOUNTS.get(key)
    if of is None:
        return plain
    amounts = (lambda symbols: of(symbols, lid)) if of is not None else None
    found = sized(form, labels, amounts=amounts, fixed=fixed, goal=goal, equal=equal)
    if found is None and goal is not None:
        # A best the description leaves unsettled (sizes left free): drawn without it.
        found = sized(form, labels, amounts=amounts, fixed=fixed, equal=equal)
    if found is None or not _reply_agrees(found, labels, question) or not _worked(found, labels):
        return plain  # nothing worked out to show: the shape in its own proportion
    return found


def _worked(found: Sized, labels: dict[str, Label]) -> bool:
    """Some label shows a size the server worked out ("x = 4", "r ≈ 4.3 cm"), or the model's
    own number where the server works the part out to it."""
    return any(
        label.value is None and (label.claimed is not None or found.shown[part] != label.text)
        for part, label in labels.items()
        if part in found.shown
    )


def _reply_agrees(found: Sized, labels: dict[str, Label], question: Question) -> bool:
    """Every size worked from an amount is the reply's own: the letter it labels is worked
    out to that value in the reply ("r ≈ 4.30 cm"). A best worked from the model's reading of
    the question (a field fenced on three sides read as four) is no answer the reply gives."""
    for part, label in labels.items():
        if label.value is not None or found.shown.get(part, label.text) == label.text:
            continue
        size = found.lengths[part] / float(label.coefficient)
        if label.letter is not None and not question.agrees(label.letter, size):
            return False
        if label.letter is None and not any(
            question.agrees(letter, size) for letter, _v, _p in question.reply_values
        ):
            return False
    return True


def _its_part(part: str, label: Label, roles: list[str], question: Question) -> bool:
    """A stated size the question names ("radius 5 cm", "12 m long") goes on that part
    only: a cone's 12 cm height is never its radius, nor its 13 cm slant its height."""
    if label.value is None:
        return True
    return stated_on({PART_ROLES.get(part, part)}, label.value, roles, question)


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
    question = read_question(texts, reply)
    items = read_items(description)
    kind = description.kind
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
