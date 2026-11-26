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

Each arrow's size must be a quantity the question states, of the quantity's kind; of two
equal values, the one whose direction agrees. Its direction must be one the question gives
that very value (``headings``: "due North" goes with the 20 m/s it is written beside; a wind
"from the west" points east), or an angle to an earlier arrow the question states ("at right
angles to each other"). Its mass must be the one the question gives that body, and its name
one the question writes for it (else the arrow goes unnamed). A picture of bodies is of them
before they collide: a velocity the question states after the collision is no arrow of it.
Every other value of the kind the question gives a direction is drawn: a before-collision
picture with one car is no picture of it. One arrow that does not check draws nothing at
all, since a picture missing an arrow says something else.

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
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.scene_drawing.headings import (
    Mention,
    Relative,
    owner,
    read_heading,
    sentence_at,
    stated_headings,
    states_angle,
    writes_a_direction,
)
from app.modules.physics.scene_drawing.values import Stated, dimension_of
from app.modules.physics.scene_drawing.vector_layout import SI_UNITS, Arrow, laid_out
from app.modules.physics.schemas import SimulationBlockSpec
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

Quantity = Literal["velocity", "force", "displacement", "momentum"]
# A value stated once that two arrows share: "two forces of 10 N each", "each of mass 2 kg".
_SHARED = re.compile(r"\b(?:each|both|identical)\b", re.IGNORECASE)
# The bodies stick after the collision: the one "after" a description may ask for.
_TOGETHER = re.compile(
    r"\b(?:together|stick(?:s|ing)?|stuck|lock(?:s|ed)?|coalesce[sd]?|combine[sd]?|coupled?"
    r"|join(?:s|ed)?|embed(?:s|ded)?|as\s+one|hold(?:s|ing)?\s+on(?:to)?|grab(?:s|bed)?"
    r"|cling(?:s|ing)?)\b",
    re.IGNORECASE,
)
# A value stated once the bodies have collided: "After the collision the first ball moves
# at 1 m/s to the left", "... and then rebounds at 2 m/s".
_AFTER = re.compile(
    r"\b(?:after(?:wards)?|subsequently|rebound\w*|bounces?\s+back|recoils?|final(?:ly)?)\b",
    re.IGNORECASE,
)
_ANGLE_TOLERANCE = 0.5
# Bodies a picture holds (``SimulationBlockSpec.bodies``).
_MOST_BODIES = 4


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
    # Five arrows and their resultant: the six a scene draws, one stage each.
    arrows: list[_Arrow] = Field(min_length=1, max_length=5)
    resultant: bool = False
    after: Literal["together"] | None = None
    part: str | None = None  # the part a reply in parts draws it for (``drawing_turn``)


@dataclass
class _Read:
    """The question's quantities of the picture's kind, the directions it gives each, the
    masses it gives each body (all keyed by the start of the value they describe), and the
    values it states after a collision."""

    stated: Stated
    givens: list[Given]
    ends: list[int]
    headings: dict[int, list[Mention]]
    masses: dict[int, list[int]]
    after: frozenset[int]
    used: set[int] = field(default_factory=set)
    used_masses: set[int] = field(default_factory=set)

    @classmethod
    def of(cls, text: str, sample: str) -> _Read:
        stated = Stated.of(text)
        kind = dimension_of(sample)
        givens = [given for given in stated.left if given.dimension == kind]
        ends = [stated.after_at(given) for given in givens]
        masses: dict[int, list[int]] = {}
        for mass in (g for g in stated.left if g.dimension == dimension_of("kg")):
            body = _owner_of(stated.text, mass.start, stated.after_at(mass), givens, ends)
            if body is not None:
                masses.setdefault(body.start, []).append(mass.start)
        after = frozenset(g.start for g in givens if _stated_after(stated.text, g))
        heads = stated_headings(stated.text, givens, ends)
        return cls(stated, givens, ends, heads, masses, after)

    def label(self, given: Given) -> str:
        return self.stated.text[given.start : self.stated.after_at(given)].strip()


def _owner_of(
    text: str, start: int, end: int, givens: Sequence[Given], ends: Sequence[int]
) -> Given | None:
    """The value a mass or a name describes: the nearest in its clause or sentence, else the
    first one after it ("Car A has a mass of 1000 kg. It travels north at 20 m/s.")."""
    found = owner(text, start, end, givens, ends)
    return found or next((g for g in givens if g.start >= end), None)


def _stated_after(text: str, given: Given) -> bool:
    """``given`` is a value the bodies have once they collided: its sentence says "after"
    (or "rebounds", "finally") before it."""
    low, _high = sentence_at(text, given.start)
    return _AFTER.search(text, low, given.start) is not None


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
    if described.layout == "bodies" and len(described.arrows) > _MOST_BODIES:
        return None
    read = _Read.of(question, SI_UNITS[described.quantity])
    free = _free_pair(described, question)
    arrows: list[Arrow] = []
    for index, item in enumerate(described.arrows):
        arrow = _arrow(item, index, arrows, read, described, question, free)
        if arrow is None:
            logger.info("described vectors not drawn: arrow %d (%s)", index + 1, described.layout)
            return None
        arrows.append(arrow)
    if _leaves_out(read, arrows, described.layout == "bodies"):
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
    written = (item.direction or "").strip()
    heading = read_heading(written) if written else None
    given = _taken(read, item.size, SI_UNITS[described.quantity], heading)
    # A picture of the bodies is of them before they collide.
    if given is None or (described.layout == "bodies" and given.start in read.after):
        return None
    angle, compass = _heading(written, heading, given, index, earlier, read, question, free)
    if angle is None:
        return None
    mass = None
    if item.mass is not None:
        if described.layout != "bodies":
            return None
        mass = _mass_of(read, item.mass, given)
        if mass is None:
            return None
    return Arrow(
        given=given,
        label=read.label(given),
        angle=angle,
        compass=compass,
        name=_named(item.name, given, read),
        mass=mass,
        mass_label=read.label(mass) if mass else None,
        direction=written,
        key=" ".join((item.name or "").split()).lower(),
    )


def _taken(
    read: _Read, written: str, sample: str, heading: Mention | Relative | None
) -> Given | None:
    """The stated quantity an arrow's size names: of several equal ones, the first not drawn
    yet whose stated direction agrees with the arrow's ("Car A travels north at 20 m/s. Car
    B travels west at 20 m/s"); one stated once with "each" may serve two arrows ("two
    forces of 10 N each")."""
    equal = read.stated.equal_to(written, sample)
    fresh = [g for g in equal if g.start not in read.used]
    if not fresh:
        fresh = [g for g in equal if _SHARED.search(read.stated.sentence(g))]

    def agrees(given: Given) -> bool:
        stated = read.headings.get(given.start, [])
        if isinstance(heading, Mention):
            return any(_matches(heading, mention) for mention in stated)
        return not stated

    given = next((g for g in fresh if agrees(g)), fresh[0] if fresh else None)
    if given is not None:
        read.used.add(given.start)
    return given


def _mass_of(read: _Read, written: str, body: Given) -> Given | None:
    """The mass the question gives the body whose value is ``body`` (Car A's 1000 kg, never
    Car B's); a mass stated once for every body ("two identical trolleys, each of mass
    2 kg") serves each."""
    for mass in read.stated.equal_to(written, "kg"):
        if mass.start in read.masses.get(body.start, []) and mass.start not in read.used_masses:
            read.used_masses.add(mass.start)
            return mass
        if _SHARED.search(read.stated.sentence(mass)):
            return mass
    return None


def _heading(
    written: str,
    heading: Mention | Relative | None,
    given: Given,
    index: int,
    earlier: list[Arrow],
    read: _Read,
    question: str,
    free: bool = False,
) -> tuple[float | None, bool]:
    """The arrow's angle, and whether it is a compass bearing: one the question gives its
    value, an angle to an earlier arrow the question states, or, for the first arrow of a
    question that writes no direction at all, to the right."""
    stated = read.headings.get(given.start, [])
    if isinstance(heading, Mention) and free:
        return heading.angle, heading.compass
    if isinstance(heading, Mention):
        agrees = any(_matches(heading, mention) for mention in stated)
        return (heading.angle, heading.compass) if agrees else (None, False)
    if isinstance(heading, Relative):
        named = " ".join(heading.to.split()).lower()
        to = next((a for a in earlier if a.key and a.key == named), None)
        if to is None or stated or not states_angle(question, heading.angle):
            return None, False
        return (to.angle + heading.angle) % 360.0, to.compass
    if written:
        return None, False  # a direction the grammar does not read
    # Never a default against a direction the question writes ("moving left at 3 m/s").
    return (0.0, False) if index == 0 and not writes_a_direction(question) else (None, False)


def _matches(heading: Mention, mention: Mention) -> bool:
    return heading.compass == mention.compass and _same_angle(heading.angle, mention.angle)


def _free_pair(described: _Vectors, question: str) -> bool:
    """Two arrows the question gives no direction, only the angle between them ("6 N and
    8 N at right angles"): the picture may turn them any way that keeps that angle."""
    if len(described.arrows) != 2 or writes_a_direction(question):
        return False
    headings = [read_heading(item.direction or "") for item in described.arrows]
    if not all(isinstance(heading, Mention) for heading in headings):
        return False
    one, other = (heading.angle for heading in headings if isinstance(heading, Mention))
    between = abs((one - other + 180.0) % 360.0 - 180.0)
    return 0.0 < between < 180.0 and states_angle(question, round(between, 6))


def _same_angle(one: float, other: float) -> bool:
    return abs((one - other + 180.0) % 360.0 - 180.0) <= _ANGLE_TOLERANCE


def _named(name: str | None, body: Given, read: _Read) -> str | None:
    """The arrow's name, when the question writes it for this body ("Car A" in the sentence
    of its 20 m/s); else none: the other car's name is no label of this one."""
    if not name or not name.strip():
        return None
    words = name.split()
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)"
    text = read.stated.text
    for found in re.finditer(pattern, text, re.IGNORECASE):
        named = _owner_of(text, found.start(), found.end(), read.givens, read.ends)
        if named is not None and named.start == body.start:
            return " ".join(words)[:20]
    return None


def _leaves_out(read: _Read, arrows: list[Arrow], bodies: bool) -> bool:
    """A value of the picture's kind the question gives a direction, drawn by no arrow; a
    value the bodies have after they collide is no part of their picture before."""
    drawn = {arrow.given.start for arrow in arrows}
    return any(
        start not in drawn and not (bodies and start in read.after)
        for start, mentions in read.headings.items()
        if mentions
    )


def _sticks(described: _Vectors, arrows: list[Arrow], question: str) -> bool:
    """An after-collision picture: bodies of stated masses whose velocities the question
    states, which it says stick together."""
    if described.layout != "bodies" or described.quantity != "velocity" or len(arrows) < 2:
        return False
    if any(arrow.mass is None for arrow in arrows):
        return False
    return _TOGETHER.search(question) is not None
