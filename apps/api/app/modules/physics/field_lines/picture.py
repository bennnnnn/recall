"""A checked field description, laid out and traced into a ```simulation `field` diagram.

Point charges stand in a row, left to right in the order the question names them, two
units apart; plates lie across the picture, the positive one on top unless the question
puts it below. Every coordinate here is the server's: the phone draws these polylines.

Each charge sends out lines in proportion to its size (``_LINES_PER_UNIT`` for the
largest), evenly round it and offset half a step from the row, so no line runs straight
into the neutral point between two like charges. Lines leave the positive charges along
E, and lines into a negative charge are traced back from it. A line that joins two charges is drawn
from the smaller of the two (``_drawn_from_here``).
"""

from __future__ import annotations

import itertools
import math
from typing import Literal

from app.modules.physics.fence import scene_fence
from app.modules.physics.field_lines.describe import FieldPicture
from app.modules.physics.field_lines.trace import (
    CHARGE_RADIUS,
    Box,
    Point,
    PointCharge,
    Sources,
    Strip,
    Traced,
    clipped,
    midpoint_arrow,
    neutral_points,
    simplified,
    trace,
)
from app.modules.physics.schemas import SimulationBlockSpec
from app.modules.physics.schemas.field_lines import (
    MAX_FIELD_LINES,
    MAX_LINE_POINTS,
    MAX_NEUTRAL_POINTS,
    FieldArrow,
    FieldCharge,
    FieldPlate,
    FieldSpec,
)

_SPACING = 2.0
_MARGIN = 1.7
_HALF_HEIGHT = 1.7
_LINES_PER_UNIT = 14
_SEED_RADIUS = 0.17
# An arrowhead stays this far from a charge's centre.
_ARROW_CLEAR = 0.45
# Plates: their length, the gap between them and how many lines cross it.
_PLATE_LENGTH = 4.0
_PLATE_GAP = 1.6
_PLATE_LINES = 9
_PLATE_BOX = Box(-2.6, 2.6, -1.4, 1.4)
# A line ends on a plate within this of its face.
_ON_PLATE = 0.03


def field_fence(picture: FieldPicture) -> str | None:
    """The ```simulation fence of one checked picture, or None when nothing could be drawn."""
    spec = _plates_spec(picture) if picture.positive is not None else _charges_spec(picture)
    if spec is None:
        return None
    return scene_fence(spec.model_dump(mode="json"))


def _charges_spec(picture: FieldPicture) -> SimulationBlockSpec | None:
    count = len(picture.charges)
    xs = [(index - (count - 1) / 2) * _SPACING for index in range(count)]
    sources = Sources(
        charges=tuple(
            PointCharge((x, 0.0), charge.q) for x, charge in zip(xs, picture.charges, strict=True)
        )
    )
    half_width = (count - 1) * _SPACING / 2 + _MARGIN
    view = Box(-half_width, half_width, -_HALF_HEIGHT, _HALF_HEIGHT)
    outer = view.grown(1.0)
    lines: list[list[Point]] = []
    for index, charge in enumerate(sources.charges):
        way = 1.0 if charge.q > 0 else -1.0
        for start in _seeds(charge):
            traced = trace(sources, start, way, outer)
            runs = clipped(traced.points, view)
            if not runs:
                continue
            if len(runs) == 1 and not _drawn_from_here(sources, index, traced):
                continue
            # A line that leaves the picture shows from its charge to the edge: where it
            # comes back in, another charge's own line shows it.
            run = simplified(runs[0])
            lines.append(run if way > 0 else list(reversed(run)))
    neutral = neutral_points(sources, view)
    field = _spec(
        lines,
        [charge.at for charge in sources.charges],
        charges=[
            FieldCharge(at=[x, 0.0], sign=1 if c.q > 0 else -1, radius=CHARGE_RADIUS, label=c.label)
            for x, c in zip(xs, picture.charges, strict=True)
        ],
        neutral=[[_round(x), _round(y)] for x, y in neutral][:MAX_NEUTRAL_POINTS],
        part=picture.part,
    )
    return None if field is None else _scene(field, view, _charges_alt(picture, bool(neutral)))


def _seeds(charge: PointCharge) -> list[Point]:
    count = max(2, round(_LINES_PER_UNIT * abs(charge.q)))
    step = 2 * math.pi / count
    return [
        (
            charge.at[0] + _SEED_RADIUS * math.cos((k + 0.5) * step),
            charge.at[1] + _SEED_RADIUS * math.sin((k + 0.5) * step),
        )
        for k in range(count)
    ]


def _drawn_from_here(sources: Sources, index: int, traced: Traced) -> bool:
    """A line that joins two charges inside the picture is drawn from the smaller one, where
    it is crowded least (from the positive one of two equal): drawn from both ends, the
    larger's lines would bunch on one side of the smaller, whose own field is radial close
    to it. A line that runs off the picture is its charge's alone."""
    other = traced.on_charge
    if other is None:
        return True
    here, there = abs(sources.charges[index].q), abs(sources.charges[other].q)
    if here != there:
        return here < there
    return sources.charges[index].q > 0


def _plates_spec(picture: FieldPicture) -> SimulationBlockSpec | None:
    top_sign: Literal[1, -1] = 1 if picture.positive == "top" else -1
    bottom_sign: Literal[1, -1] = -1 if top_sign > 0 else 1
    half, gap = _PLATE_LENGTH / 2, _PLATE_GAP / 2
    sources = Sources(
        strips=(
            Strip(gap, -half, half, float(top_sign)),
            Strip(-gap, -half, half, -float(top_sign)),
        )
    )
    source_y = gap if top_sign > 0 else -gap
    inward = -1.0 if top_sign > 0 else 1.0

    def on_the_other_plate(point: Point) -> Traced | None:
        if abs(point[1] + source_y) <= _ON_PLATE and abs(point[0]) <= half + _ON_PLATE:
            return Traced([], on_plate=True)
        return None

    lines: list[list[Point]] = []
    for k in range(_PLATE_LINES):
        x = -half + (k + 0.5) * _PLATE_LENGTH / _PLATE_LINES
        start = (x, source_y + inward * _ON_PLATE)
        traced = trace(sources, start, 1.0, _PLATE_BOX.grown(0.5), on_the_other_plate)
        lines.extend(_runs(traced.points, _PLATE_BOX))
    field = _spec(
        lines,
        [],
        plates=[
            FieldPlate(start=[-half, gap], end=[half, gap], sign=top_sign),
            FieldPlate(start=[-half, -gap], end=[half, -gap], sign=bottom_sign),
        ],
        part=picture.part,
    )
    alt = (
        "Field lines run straight and evenly spaced from the positive plate to the negative "
        "one, bowing out a little at the ends."
    )
    return None if field is None else _scene(field, _PLATE_BOX, alt)


def _runs(points: list[Point], view: Box) -> list[list[Point]]:
    """A traced line as it shows in the picture: its runs inside it, simplified."""
    return [simplified(run) for run in clipped(points, view) if len(run) >= 2]


def _spec(
    lines: list[list[Point]],
    avoid: list[Point],
    *,
    charges: list[FieldCharge] | None = None,
    plates: list[FieldPlate] | None = None,
    neutral: list[list[float]] | None = None,
    part: str | None,
) -> FieldSpec | None:
    kept = [line for line in lines if _length(line) > 0.05][:MAX_FIELD_LINES]
    if not kept or any(len(line) > MAX_LINE_POINTS for line in kept):
        return None
    arrows = []
    for line in kept:
        placed = midpoint_arrow(line, tuple(avoid), _ARROW_CLEAR)
        if placed is not None:
            (x, y), (dx, dy) = placed
            arrows.append(FieldArrow(at=[_round(x), _round(y)], dx=_round(dx), dy=_round(dy)))
    try:
        return FieldSpec(
            charges=charges or [],
            plates=plates or [],
            lines=[[[_round(x), _round(y)] for x, y in line] for line in kept],
            arrows=arrows,
            neutral=neutral or [],
            part=part,
        )
    except ValueError:
        return None


def _length(line: list[Point]) -> float:
    return sum(math.dist(a, b) for a, b in itertools.pairwise(line))


def _round(value: float) -> float:
    return round(value, 3)


def _scene(field: FieldSpec, view: Box, alt: str) -> SimulationBlockSpec:
    return SimulationBlockSpec(
        type="field",
        title="Electric Field",
        title_key="electric_field",
        x_min=view.x_min,
        x_max=view.x_max,
        y_min=view.y_min,
        y_max=view.y_max,
        field=field,
        alt=alt,
    )


def _charges_alt(picture: FieldPicture, neutral: bool) -> str:
    """One sentence a screen reader says: what the lines do, from the signs alone, for each
    arrangement: one positive charge, one negative, an unlike pair, a like pair, three."""
    positive = sum(charge.q > 0 for charge in picture.charges)
    count = len(picture.charges)
    still = ", leaving a neutral point where the field is zero" if neutral else ""
    if count == 1 and positive == 1:
        return "Field lines point straight out from the positive charge, spreading apart."
    if count == 1:
        return "Field lines point straight in to the negative charge, closing together."
    if count == 2 and positive == 1:
        return "Field lines leave the positive charge and curve round to end on the negative one."
    if count == 2:
        way = "away from" if positive == 2 else "in toward"
        return f"Field lines point {way} each charge and bend apart{still}."
    return (
        f"Field lines run from the {positive} positive to the {count - positive} negative of "
        f"three charges in a row, out to the edge where they do not end on one{still}."
        if 0 < positive < count
        else f"Field lines point {'away from' if positive else 'in toward'} each of three "
        f"charges in a row and bend apart{still}."
    )
