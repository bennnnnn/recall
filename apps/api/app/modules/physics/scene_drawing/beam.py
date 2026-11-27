"""A bar with forces at points along it, as a figure read describes it, each value checked.

Moments questions ("What are the moments about P and Q? [a horizontal bar: 5 N down at the
left end; P 5 cm to its right; 8 N down 10 cm right of P; Q 10 cm further]") are taught from
the bar's picture, and no solver reads one with three or more forces, so none was drawn
(textbook round, 2026-11-25). The read names the marks along the bar, left to right, never a
coordinate:

    {"kind": "beam", "marks": [
        {"forces": [{"size": "5 N", "direction": "down"}]},
        {"name": "P", "gap": "5 cm"},
        {"gap": "10 cm", "forces": [{"size": "8 N", "direction": "down"}]},
        {"name": "Q", "gap": "10 cm"}]}

Every distance must be a length the question states (each statement used once), or the
letter of one it asks for ("x"); every force a force the question states, with the direction
written beside it in its sentence, a mass hung there (its weight is down), or the letter of an
unknown force the question writes. Every force and mass the question states must be drawn: a
bar missing a force says something else. One value that does not check draws nothing. The
server lays the bar out to scale, the arrows at their points, the distances as dimension lines.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.display import GIVEN_FIGURES, plain_quantity
from app.modules.physics.scene_drawing.values import Stated, dimension_of
from app.modules.physics.schemas import SimulationBlockSpec, SimulationBody, SimulationVector
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

_FORCE = dimension_of("N")
_MASS = dimension_of("kg")
_LENGTH = dimension_of("m")
_G = 9.81
# One letter the question writes for an unknown: "a distance x", "a force F".
_LETTER = re.compile(r"[A-Za-z]")
# A direction a sentence gives a force: up or down, as a bar's forces are.
_DIRECTION = re.compile(r"\b(?:up|upward|upwards|down|downward|downwards)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.;?!](?!\d)")
# Where a force's clause ends: a stop or a comma, never "and" ("B = 10 N downwards and C =
# 10 N upwards both act at point X" is one clause of X's).
_CLAUSE_STOP = re.compile(r"[.;?!,](?!\d)")
# A force's own part of its clause: up to a stop, a comma or an "and".
_PART_STOP = re.compile(r"[.;?!,](?!\d)|\band\b", re.IGNORECASE)
# A value written straight after "the" names one stated elsewhere ("the 8 N force").
_THE = re.compile(r"\bthe[ \t]+$", re.IGNORECASE)
# Where a clause of one sentence ends: a comma or "and" between two forces.
_CLAUSE_END = re.compile(r"[.;?!,](?!\d)|\band\b", re.IGNORECASE)
# The arrows and dimension lines a scene draws (``SimulationBlockSpec.vectors``).
_MOST_VECTORS = 6
_MOST_POINTS = 4


class _BeamForce(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=3)
    size: str = Field(max_length=30)
    direction: Literal["up", "down"]


class _Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=3)
    gap: str | None = Field(default=None, max_length=30)
    at: str | None = Field(default=None, max_length=30)
    pivot: bool = False
    forces: list[_BeamForce] = Field(default_factory=list, max_length=3)


class _Beam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["beam"]
    marks: list[_Mark] = Field(min_length=2, max_length=6)
    part: str | None = None


@dataclass(frozen=True)
class _Length:
    """A distance along the bar: its size in metres (None for the letter of an unknown one)
    and its label."""

    si: float | None
    label: str
    # Where the question writes it: its value, or the letter of an unknown one.
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class _Measure:
    """A dimension line from one mark to another, with its stated distance."""

    start: int
    end: int
    label: str


@dataclass(frozen=True)
class _Load:
    """A checked force at a mark: its size in newtons (None for an unknown), up or not."""

    si: float | None
    label: str
    up: bool


# Each mark's place along the bar, the dimension lines and each mark's forces.
_Layout = tuple[list[float], list[_Measure], list[list[_Load]]]


def described_beam(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The bar one block describes, drawn; none when it is no beam block or any value does
    not check against the question (``texts[0]``)."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, dict) or data.get("kind") != "beam":
        return []
    try:
        described = _Beam.model_validate(data)
    except ValidationError as exc:
        logger.info("described beam not read: %s", exc.errors()[0].get("loc"))
        return []
    stated = Stated.of(texts[0] if texts else "")
    laid = _laid_out(described, stated)
    if laid is None:
        return []
    try:
        return [_scene(described, *laid)]
    except ValueError as exc:  # a layout the scene schema refuses is no picture
        logger.info("described beam not drawn: %s", exc)
        return []


def _laid_out(described: _Beam, stated: Stated) -> _Layout | None:
    """Each mark's place along the bar, the distance before it, and its checked forces; None
    when one does not check, a stated force or mass is left out, or the marks go backwards."""
    if described.marks[0].gap or described.marks[0].at:
        logger.info("described beam not drawn: its first mark has a distance")
        return None
    lengths: list[_Length] = []
    for mark in described.marks[1:]:
        if mark.gap is not None and mark.at is not None:
            return _refused("a mark with two distances")
        written = mark.gap if mark.gap is not None else mark.at
        # A mark the read gives no distance is at one the question does not say: drawn
        # between its neighbours with no length written on it, never a length of its own.
        length = _Length(None, "") if written is None else _length(stated, written)
        if length is None:
            return _refused("a distance the question does not state")
        lengths.append(length)
    places = _places(described.marks[1:], lengths)
    if places is None:
        return _refused("marks out of order")
    measures = [
        _Measure(index if mark.at is None else 0, index + 1, length.label)
        for index, (mark, length) in enumerate(zip(described.marks[1:], lengths, strict=True))
        if length.label
    ]
    loads: list[list[_Load]] = []
    for index, mark in enumerate(described.marks):
        tied = _Ties(stated.text, described.marks, lengths, index)
        checked = [_load(stated, force, tied) for force in mark.forces]
        if any(load is None for load in checked):
            return _refused("a force the question does not state at its mark")
        loads.append([load for load in checked if load is not None])
    # A force or mass the question states again ("the 8 N force", "the 2.5 kg mass") is one
    # the bar already holds.
    if any(g.dimension in (_FORCE, _MASS) and not stated.restated(g) for g in stated.left):
        return _refused("a stated force or mass left out")
    if not any(loads):
        return _refused("no force")
    return places, measures, loads


def _places(marks: Sequence[_Mark], lengths: Sequence[_Length]) -> list[float] | None:
    """Each mark's place from the first, in metres: a gap from the mark before, an "at" from
    the first. A distance the question asks for is drawn between its neighbours (midway to
    the next mark placed from the first, else one typical gap on); None when the marks go
    backwards."""
    stated = [length.si for length in lengths if length.si is not None]
    typical = sum(stated) / len(stated) if stated else 1.0
    places: list[float] = [0.0]
    for index, (mark, length) in enumerate(zip(marks, lengths, strict=True)):
        if length.si is not None:
            place = places[-1] + length.si if mark.gap is not None else length.si
        else:
            ahead = next(
                (
                    later.si
                    for later_mark, later in zip(
                        marks[index + 1 :], lengths[index + 1 :], strict=True
                    )
                    if later.si is not None and later_mark.at is not None
                ),
                None,
            )
            place = (places[-1] + ahead) / 2 if ahead is not None else places[-1] + typical
        if place <= places[-1]:
            return None
        places.append(place)
    return places


def _refused(why: str) -> _Layout | None:
    logger.info("described beam not drawn: %s", why)
    return None


def _length(stated: Stated, written: str) -> _Length | None:
    """A distance the question states (taken, so each statement serves once), or the letter
    of one it asks for."""
    letter = _letter(stated.text, written)
    if letter is not None:
        at = _token(letter).search(stated.text)
        return _Length(None, letter, at.span() if at else None)
    given = stated.take(written, "m")
    if given is None or given.si is None or given.si <= 0:
        return None
    return _Length(given.si, _label(given), (given.start, given.end))


def _letter(text: str, written: str) -> str | None:
    """``written`` is one letter the question writes on its own ("a distance x", "force F")."""
    letter = written.strip()
    if _LETTER.fullmatch(letter) is None:
        return None
    return letter if re.search(rf"(?<![\w']){re.escape(letter)}(?![\w'])", text) else None


def _token(letter: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w']){re.escape(letter)}(?![\w'])")


# What names a bar's ends, its pivot, and the side a distance is measured to.
_LEFT_END = re.compile(r"\bleft(?:[\s-]hand)?(?:[\s-]most)?\s+end\b", re.IGNORECASE)
_RIGHT_END = re.compile(r"\bright(?:[\s-]hand)?(?:[\s-]most)?\s+end\b", re.IGNORECASE)
_PIVOT = re.compile(r"\b(?:pivot|balance\s+point|axis|fulcrum|hinge)\b", re.IGNORECASE)
# "2 m to the left of the pivot", "1.5 m to its left", "10 cm right of P": the side of the
# gap the measured thing is on, read just after the distance.
_SIDE = re.compile(
    r"^[\w\s]{0,20}?\b(?:to\s+(?:the|its|their)\s+|on\s+the\s+)?(left|right)\b", re.IGNORECASE
)
_SIDE_REACH = 30
# A length that is the whole bar's: "30 cm long", "45 cm in length".
_WHOLE = re.compile(r"\s*(?:[a-zμ]{1,3}\s+)?(?:long\b|in\s+length\b)", re.IGNORECASE)


@dataclass(frozen=True)
class _Ties:
    """What ties a force to its mark in the question's words, and to which mark.

    The evidence in a clause is each mark's letter, "left end" (the first mark) and "right
    end" (the last), and each distance the bar is laid out by, given to the mark on the side
    it is measured to: "a 3 kg mass 1.5 m to the left of the pivot" gives the 1.5 m to the
    mark left of the pivot, "x to the right" the one right of it; a distance with no side is
    its own mark's. A force is held to its mark when the evidence nearest it in its clause is
    that mark's: so two forces swapped, the masses of a see-saw swapped or the gaps swapped
    draw nothing (review of #2603). The pivot's name ties only a force at the pivot, and only
    when nothing else in its clause does."""

    text: str
    marks: Sequence[_Mark]
    lengths: Sequence[_Length]
    index: int

    def _evidence(self, begin: int, finish: int) -> list[tuple[int, int, int]]:
        """(start, end, mark) of every tie in the clause between ``begin`` and ``finish``."""
        found: list[tuple[int, int, int]] = []
        for at, mark in enumerate(self.marks):
            name = (mark.name or "").strip()
            if name and _LETTER.fullmatch(name):
                found += [(m.start(), m.end(), at) for m in _token(name).finditer(self.text)]
        last = len(self.marks) - 1
        found += [(m.start(), m.end(), 0) for m in _LEFT_END.finditer(self.text)]
        found += [(m.start(), m.end(), last) for m in _RIGHT_END.finditer(self.text)]
        for at, length in enumerate(self.lengths, start=1):
            spans = [length.span] if length.si is not None else _letter_spans(self.text, length)
            for span in spans:
                # "a rod 30 cm long": the whole bar's length is no mark's.
                if span is not None and not _WHOLE.match(self.text, span[1]):
                    found.append((*span, self._measured(at, span[1])))
        return [item for item in found if begin <= item[0] < finish]

    def _measured(self, at: int, after: int) -> int:
        """The mark a distance belongs to: mark ``at`` (whose distance it is), or the mark
        before it when the words say the measured thing is to the left."""
        side = _SIDE.match(self.text[after : after + _SIDE_REACH])
        gap = self.marks[at].at is None
        if side is not None and gap and side.group(1).lower() == "left":
            return at - 1
        return at

    def hold(self, start: int, end: int) -> bool:
        # Its own part of the sentence first ("a 6 N force at its left end and a 9 N force at
        # its right end": each between its "and"s), else the clause between commas ("B = 10
        # N downwards and C = 10 N upwards both act at point X").
        evidence: list[tuple[int, int, int]] = []
        for stops in (_PART_STOP, _CLAUSE_STOP):
            begin = max((m.end() for m in stops.finditer(self.text, 0, start)), default=0)
            stop = stops.search(self.text, end)
            finish = stop.start() if stop else len(self.text)
            found = self._evidence(begin, finish)
            evidence = [item for item in found if not start <= item[0] < end]
            if evidence:
                break
        if not evidence:
            mark = self.marks[self.index]
            return mark.pivot and _PIVOT.search(self.text, begin, finish) is not None
        nearest = min(evidence, key=lambda item: max(item[0] - end, start - item[1]))
        distance = max(nearest[0] - end, start - nearest[1])
        rivals = {item[2] for item in evidence if max(item[0] - end, start - item[1]) == distance}
        return rivals == {self.index}


def _letter_spans(text: str, length: _Length) -> list[tuple[int, int]]:
    """Every place the question writes an unknown distance's letter ("a distance x")."""
    if length.si is not None or not length.label:
        return []
    return [m.span() for m in _token(length.label).finditer(text)]


def _load(stated: Stated, force: _BeamForce, ties: _Ties) -> _Load | None:
    up = force.direction == "up"
    letter = _letter(stated.text, force.size)
    if letter is not None:
        at = next(
            (m for m in _token(letter).finditer(stated.text) if ties.hold(m.start(), m.end())),
            None,
        )
        if at is None:
            return None
        said = _said_direction(stated.text, at.start(), at.end())
        if said is not None and said != up:
            return None
        return _Load(None, _named(force.name, letter), up)
    for kind, sample in ((_FORCE, "N"), (_MASS, "kg")):
        candidates = stated.equal_to(force.size, sample)
        if not candidates:
            continue
        if kind == _MASS and up:
            return None  # a hung mass pulls the bar down
        agreeing = [
            given
            for given in candidates
            if (kind == _MASS or _said_direction(stated.text, given.start, given.end) == up)
            and ties.hold(given.start, given.end)
        ]
        if not agreeing:
            return None
        # Its statement ("a 2.5 kg mass a distance x to the right"), before a sentence that
        # names it again ("the distance of the 2.5 kg mass"), whichever comes first.
        given = min(agreeing, key=lambda g: _THE.search(stated.text, 0, g.start) is not None)
        stated.left.remove(given)
        stated.taken.append(given)
        newtons = (given.si or given.value) * (_G if kind == _MASS else 1.0)
        return _Load(newtons, _named(force.name, _label(given)), up)
    return None


def _said_direction(text: str, start: int, end: int) -> bool | None:
    """Up (True) or down (False): the direction word of the value's own clause ("50 N acts
    downwards at A, 80 N acts upwards at B": each between its commas), else the nearest in
    its sentence; None when its sentence gives none."""
    for stops in (_CLAUSE_END, _SENTENCE_END):
        begin = max((m.end() for m in stops.finditer(text, 0, start)), default=0)
        stop = stops.search(text, end)
        finish = stop.start() if stop else len(text)
        words = list(_DIRECTION.finditer(text, begin, finish))
        if words:
            nearest = min(words, key=lambda m: min(abs(m.start() - end), abs(start - m.end())))
            return nearest.group().lower().startswith("up")
    return None


def _named(name: str | None, label: str) -> str:
    named = (name or "").strip()
    return f"{named} = {label}"[:24] if named and named != label else label[:24]


def _overlap(one: _Measure, other: _Measure) -> bool:
    return one.start < other.end and other.start < one.end


def _label(given: Given) -> str:
    return plain_quantity(given.value, given.unit, GIVEN_FIGURES)


def _scene(
    described: _Beam,
    places: list[float],
    lines: list[_Measure],
    loads: list[list[_Load]],
) -> SimulationBlockSpec:
    span = places[-1]
    mid = span / 2
    xs = [place - mid for place in places]
    known = [load.si for mark in loads for load in mark if load.si is not None]
    typical = sum(known) / len(known) if known else 1.0
    vectors = [
        SimulationVector(
            anchor=[x, 0.0],
            dx=0.0,
            dy=(load.si or typical) * (1.0 if load.up else -1.0),
            label=load.label,
            role="force",
        )
        for x, mark in zip(xs, loads, strict=True)
        for load in mark
    ]
    # Dimension lines above the bar, each a step above the lines it spans, so two measured
    # from one end ("20 cm from P", "50 cm from P") never lie on each other.
    rise, step = span * 0.16, span * 0.1
    levels: list[int] = []
    for at, line in enumerate(lines):
        under = [levels[i] for i, other in enumerate(lines[:at]) if _overlap(other, line)]
        levels.append(max(under, default=-1) + 1)
    measures = [
        SimulationVector(
            anchor=[xs[line.start], rise + step * level],
            dx=xs[line.end] - xs[line.start],
            dy=0.0,
            label=line.label,
            role="measure",
        )
        for line, level in zip(lines, levels, strict=True)
    ]
    if len(vectors) + len(measures) <= _MOST_VECTORS:
        vectors += measures
    # One pivot is drawn as a wedge under the bar. Two marked as pivots ("the moments about P
    # and about Q") are points moments are taken about, each a lettered point.
    pivots = [x for x, mark in zip(xs, described.marks, strict=True) if mark.pivot]
    pivot = pivots[0] if len(pivots) == 1 else None
    points = [
        SimulationBody(
            path=[[x, 0.0], [x, 0.0]],
            radius=span * 0.012,
            label=mark.name.strip(),
            role="secondary",
        )
        for x, mark in zip(xs, described.marks, strict=True)
        if mark.name and mark.name.strip()
    ][:_MOST_POINTS]
    reach = span * 0.6
    forces = ", ".join(v.label or "" for v in vectors if v.role == "force")
    return SimulationBlockSpec(
        type="lever",
        title="Moments",
        title_key="moments",
        alt=f"A bar with forces along it: {forces}."[:300],
        beam=[xs[0], 0.0, xs[-1], 0.0],
        pivot=[pivot, 0.0] if pivot is not None else None,
        bodies=points,
        vectors=vectors,
        x_min=-reach,
        x_max=reach,
        y_min=-span * 0.4,
        y_max=span * 0.4,
    )
