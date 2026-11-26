"""Arrows a reply describes: velocities, forces, displacements or momenta, as the question
states them, checked one by one and drawn by the server.

"Car A of mass 1000 kg travels at 20 m/s due North. Car B of mass 1300 kg travels due West
at 16 m/s ... First draw a diagram of the cars before collision" was read by no solver, and
the scene vocabulary has no two bodies meeting at a junction: the reply said "I couldn't draw
this diagram" (live, 2026-11-25). The picture is only the question's arrows, so the reply
names them in a ```draw block, never a coordinate:

    {"kind": "vectors", "layout": "bodies", "quantity": "velocity",
     "arrows": [{"name": "Car A", "size": "20 m/s", "direction": "north", "mass": "1000 kg"},
                {"name": "Car B", "size": "16 m/s", "direction": "west", "mass": "1300 kg"}]}

Each arrow's size must be a quantity the question states, of the quantity's kind; its
direction one the question gives that very value (``headings``: "due North" goes with the
20 m/s it is written beside), or an angle to an earlier arrow the question states ("at right
angles to each other"); a mass one the question states; a name the question writes (else the
arrow goes unnamed). Every value of the kind the question gives a direction is drawn: a
before-collision picture with one car is no picture of it. One arrow that does not check
draws nothing at all, since a picture missing an arrow says something else.

The server lays it out: ``bodies`` puts each body behind the meeting point, its arrow toward
it (two cars approaching a junction, two balls about to meet); ``tail`` draws every arrow from
one point (forces on a point, a boat's heading and the current); ``chain`` draws them head to
tail (a walk of legs). ``resultant`` adds their sum, worked out here; ``after: "together"``
adds the bodies moving off as one after a collision the question says they stick in, at the
velocity momentum gives them. North is up, east is right, and a compass picture stands on
N and E axes.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.scene_drawing.headings import (
    Mention,
    Relative,
    read_heading,
    stated_headings,
    states_angle,
)
from app.modules.physics.scene_drawing.values import Stated, dimension_of
from app.modules.physics.scene_drawing.vector_layout import Arrow, laid_out
from app.modules.physics.schemas import SimulationBlockSpec
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

Quantity = Literal["velocity", "force", "displacement", "momentum"]
# A unit of each quantity's kind, and the SI unit its worked-out values are written in.
SAMPLES: dict[str, str] = {
    "velocity": "m/s",
    "force": "N",
    "displacement": "m",
    "momentum": "kg m/s",
}
# A value stated once that two arrows share: "two forces of 10 N each".
_SHARED = re.compile(r"\b(?:each|both)\b", re.IGNORECASE)
# The bodies stick after the collision: the one "after" a description may ask for.
_TOGETHER = re.compile(
    r"\b(?:together|stick(?:s|ing)?|stuck|lock(?:s|ed)?|coalesce[sd]?|combine[sd]?|coupled?"
    r"|join(?:s|ed)?|embed(?:s|ded)?|as\s+one|hold(?:s|ing)?\s+on(?:to)?|grab(?:s|bed)?"
    r"|cling(?:s|ing)?)\b",
    re.IGNORECASE,
)
_ANGLE_TOLERANCE = 0.5


class _Arrow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=40)
    size: str = Field(max_length=40)
    direction: str | None = Field(default=None, max_length=60)
    mass: str | None = Field(default=None, max_length=40)


class _Vectors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["vectors"]
    layout: Literal["bodies", "tail", "chain"]
    quantity: Quantity
    arrows: list[_Arrow] = Field(min_length=1, max_length=4)
    resultant: bool = False
    after: Literal["together"] | None = None
    part: str | None = None  # the part a reply in parts draws it for (``drawing_turn``)


@dataclass
class _Read:
    """The question's quantities and the directions it gives each."""

    stated: Stated
    headings: dict[int, list[Mention]]

    @classmethod
    def of(cls, text: str, sample: str) -> _Read:
        stated = Stated.of(text)
        kind = dimension_of(sample)
        givens = [given for given in stated.left if given.dimension == kind]
        ends = [stated.after_at(given) for given in givens]
        return cls(stated, stated_headings(stated.text, givens, ends))


def described_vectors(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The arrows one ```draw block describes, drawn; none when it is no vectors block or
    any arrow does not check against the question (``texts[0]``)."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, dict) or data.get("kind") != "vectors":
        return []
    try:
        described = _Vectors.model_validate(data)
    except ValidationError as exc:
        logger.info("described vectors not read: %s", exc.errors()[0].get("loc"))
        return []
    question = texts[0] if texts else ""
    arrows = _checked(described, question)
    if arrows is None:
        return []
    # An after the question does not state is left out; the arrows it states still draw.
    after = described.after is not None and _sticks(described, arrows, question)
    if described.after is not None and not after:
        logger.info("described vectors: no after drawn, the question states none")
    try:
        return laid_out(
            arrows, described.layout, described.quantity, described.resultant, question, after
        )
    except ValueError as exc:  # a layout the scene schema refuses is no picture
        logger.info("described vectors not drawn: %s", exc)
        return []


def _checked(described: _Vectors, question: str) -> list[Arrow] | None:
    """Every arrow held to the question, or None when one is not."""
    read = _Read.of(question, SAMPLES[described.quantity])
    free = _free_pair(described, read, question)
    arrows: list[Arrow] = []
    for index, item in enumerate(described.arrows):
        arrow = _arrow(item, index, arrows, read, described, question, free)
        if arrow is None:
            logger.info("described vectors not drawn: arrow %d (%s)", index + 1, described.layout)
            return None
        arrows.append(arrow)
    if _leaves_out(read, arrows):
        logger.info("described vectors not drawn: a stated %s left out", described.quantity)
        return None
    return arrows


def _arrow(
    item: _Arrow,
    index: int,
    earlier: list[Arrow],
    read: _Read,
    described: _Vectors,
    question: str,
    free: bool = False,
) -> Arrow | None:
    given = _taken(read.stated, item.size, SAMPLES[described.quantity])
    if given is None:
        return None
    angle, compass = _heading(item.direction, given, index, earlier, read, question, free)
    if angle is None:
        return None
    mass = None
    if item.mass is not None:
        if described.layout != "bodies":
            return None
        mass = read.stated.take(item.mass, "kg")
        if mass is None:
            return None
    return Arrow(
        given=given,
        label=read.stated.text[given.start : read.stated.after_at(given)].strip(),
        angle=angle,
        compass=compass,
        name=_named(item.name, question),
        mass=mass,
        mass_label=(
            read.stated.text[mass.start : read.stated.after_at(mass)].strip() if mass else None
        ),
        direction=(item.direction or "").strip(),
        key=" ".join((item.name or "").split()).lower(),
    )


def _taken(stated: Stated, written: str, sample: str) -> Given | None:
    """The stated quantity an arrow's size names; one stated once with "each" may serve two
    arrows ("two forces of 10 N each")."""
    given = stated.take(written, sample)
    if given is not None:
        return given
    again = Stated(stated.text, list(stated.taken))
    shared = again.take(written, sample)
    if shared is not None and _SHARED.search(stated.sentence(shared)):
        return shared
    return None


def _heading(
    direction: str | None,
    given: Given,
    index: int,
    earlier: list[Arrow],
    read: _Read,
    question: str,
    free: bool = False,
) -> tuple[float | None, bool]:
    """The arrow's angle, and whether it is a compass bearing: one the question gives its
    value, an angle to an earlier arrow the question states, or, for the first arrow of a
    value the question gives no direction, to the right."""
    stated = read.headings.get(given.start, [])
    heading = read_heading(direction) if direction and direction.strip() else None
    if isinstance(heading, Mention) and free:
        return heading.angle, heading.compass
    if isinstance(heading, Mention):
        agrees = any(
            heading.compass == mention.compass and _same_angle(heading.angle, mention.angle)
            for mention in stated
        )
        return (heading.angle, heading.compass) if agrees else (None, False)
    if isinstance(heading, Relative):
        named = " ".join(heading.to.split()).lower()
        to = next((a for a in earlier if a.key and a.key == named), None)
        if to is None or stated or not states_angle(question, heading.angle):
            return None, False
        return (to.angle + heading.angle) % 360.0, to.compass
    if direction and direction.strip():
        return None, False  # a direction the grammar does not read
    return (0.0, False) if index == 0 and not stated else (None, False)


def _free_pair(described: _Vectors, read: _Read, question: str) -> bool:
    """Two arrows the question gives no direction, only the angle between them ("6 N and
    8 N at right angles"): the picture may turn them any way that keeps that angle."""
    if len(described.arrows) != 2 or any(read.headings.values()):
        return False
    headings = [read_heading(item.direction or "") for item in described.arrows]
    if not all(isinstance(heading, Mention) for heading in headings):
        return False
    one, other = (heading.angle for heading in headings if isinstance(heading, Mention))
    between = abs((one - other + 180.0) % 360.0 - 180.0)
    return 0.0 < between < 180.0 and states_angle(question, round(between, 6))


def _same_angle(one: float, other: float) -> bool:
    return abs((one - other + 180.0) % 360.0 - 180.0) <= _ANGLE_TOLERANCE


def _named(name: str | None, question: str) -> str | None:
    """The arrow's name, when the question writes it ("Car A"); else none."""
    if not name or not name.strip():
        return None
    words = " ".join(name.split())
    if re.search(rf"(?<!\w){re.escape(words)}(?!\w)", " ".join(question.split()), re.I) is None:
        return None
    return words[:20]


def _leaves_out(read: _Read, arrows: list[Arrow]) -> bool:
    """A value of the picture's kind the question gives a direction, drawn by no arrow."""
    drawn = {arrow.given.start for arrow in arrows}
    return any(start not in drawn for start, mentions in read.headings.items() if mentions)


def _sticks(described: _Vectors, arrows: list[Arrow], question: str) -> bool:
    """An after-collision picture: bodies of stated masses whose velocities the question
    states, which it says stick together."""
    if described.layout != "bodies" or described.quantity != "velocity" or len(arrows) < 2:
        return False
    if any(arrow.mass is None for arrow in arrows):
        return False
    return _TOGETHER.search(question) is not None
