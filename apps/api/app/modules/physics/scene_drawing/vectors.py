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

from app.modules.physics.display import GIVEN_FIGURES, plain_quantity
from app.modules.physics.scene_drawing.components import component_arrow, left_out
from app.modules.physics.scene_drawing.headings import (
    Mention,
    Relative,
    read_heading,
    stated_headings,
    states_angle,
    writes_a_direction,
)
from app.modules.physics.scene_drawing.ties import (
    label_before,
    label_of,
    stated_after,
    stick_together,
    tie,
)
from app.modules.physics.scene_drawing.values import Stated, dimension_of
from app.modules.physics.scene_drawing.vector_layout import SI_UNITS, Arrow, laid_out
from app.modules.physics.schemas import SimulationBlockSpec
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

Quantity = Literal["velocity", "force", "displacement", "momentum"]
# A value stated once that two arrows share: "two forces of 10 N each", "each of mass 2 kg".
_SHARED = re.compile(r"\b(?:each|both|identical)\b", re.IGNORECASE)
_ANGLE_TOLERANCE = 0.5
_RELATIVE_TO = re.compile(r"\brelative\s+(?:to|velocity)\b", re.IGNORECASE)
# An angle is a direction's own number ("30° above the horizontal"), never a value it
# describes; a mass and a pure number have no direction.
_NO_DIRECTION = frozenset({dimension_of("°"), dimension_of("kg"), None})
# Bodies a picture holds (``SimulationBlockSpec.bodies``).
_MOST_BODIES = 4


class _Arrow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=40)
    size: str = Field(default="", max_length=40)
    # A vector the question writes by its components ("[4 5]"), in place of size and
    # direction (``components``).
    components: str | None = Field(default=None, max_length=40)
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
    # How many masses the question states: one stated "each" for every body is shared.
    masses_stated: int = 0
    used: set[int] = field(default_factory=set)
    used_masses: set[int] = field(default_factory=set)

    @classmethod
    def of(cls, text: str, sample: str) -> _Read:
        stated = Stated.of(text)
        kind = dimension_of(sample)
        givens = [given for given in stated.left if given.dimension == kind]
        ends = [stated.after_at(given) for given in givens]
        kilograms = [g for g in stated.left if g.dimension == dimension_of("kg")]
        masses: dict[int, list[int]] = {}
        for mass in kilograms:
            rivals = [other for other in kilograms if other is not mass]
            label = label_before(stated.text, mass.start)
            end = stated.after_at(mass)
            body = tie(stated.text, mass.start, end, givens, label, rivals, mass.unit)
            if body is not None:
                masses.setdefault(body.start, []).append(mass.start)
        after = frozenset(g.start for g in givens if stated_after(stated.text, g))
        # A direction goes to the nearest value of any kind ("a car travelling north at
        # 20 m/s brakes with a force of 5000 N": north is the car's, not the force's), and
        # only one of the picture's kind keeps it.
        # A mass, an angle or a pure number has no direction of its own.
        every = [g for g in stated.left if g.dimension not in _NO_DIRECTION]
        heads = stated_headings(stated.text, every, [stated.after_at(g) for g in every])
        mine = {given.start for given in givens}
        heads = {start: found for start, found in heads.items() if start in mine}
        return cls(stated, givens, ends, heads, masses, after, masses_stated=len(kilograms))

    def label(self, given: Given) -> str:
        """The value as a label, written from its number and unit (a power of ten as the
        answer card writes it), never the "1.2e4" the reading folded it to."""
        return plain_quantity(given.value, given.unit, GIVEN_FIGURES)


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
    # A velocity relative to another body is their difference, never the sum a resultant
    # draws: "the velocity of Nishan relative to Melesse" got the sum's 42° north of east
    # beside a reply that worked out 42° south of east (textbook round, 2026-11-25).
    resultant = described.resultant and _RELATIVE_TO.search(question) is None
    try:
        return laid_out(arrows, described.layout, described.quantity, resultant, question, after)
    except ValueError as exc:  # a layout the scene schema refuses is no picture
        logger.info("described vectors not drawn: %s", exc)
        return []


def _checked(described: _Vectors, question: str) -> list[Arrow] | None:
    """Every arrow held to the question, or None when one is not."""
    if described.layout == "bodies" and len(described.arrows) > _MOST_BODIES:
        return None
    read = _Read.of(question, SI_UNITS[described.quantity])
    # Read as the values are read, its markup off: "$90^\circ$" is 90°.
    question = read.stated.text
    free = _free_pair(described, question)
    unit = SI_UNITS[described.quantity]
    arrows: list[Arrow] = []
    # The written vectors ("A [4 5] N") the arrows drew, by where the question writes them.
    written: set[int] = set()
    for index, item in enumerate(described.arrows):
        if item.components is not None:
            arrow = None if item.mass else component_arrow(
                item.name, item.components, unit, question, written
            )  # fmt: skip
        else:
            arrow = _arrow(item, index, arrows, read, described, question, free)
        if arrow is None:
            logger.info("described vectors not drawn: arrow %d (%s)", index + 1, described.layout)
            return None
        arrows.append(arrow)
    if described.layout == "bodies" and _one_body_twice(arrows):
        logger.info("described vectors not drawn: two velocities of one way, no body named")
        return None
    if _leaves_out(read, arrows, described.layout == "bodies") or (
        written and left_out(question, written, unit)
    ):
        logger.info("described vectors not drawn: a stated %s left out", described.quantity)
        return None
    return arrows


def _one_body_twice(arrows: list[Arrow]) -> bool:
    """Two arrows the same way, one of them of no named or weighed body: they may be one
    body's velocity at two times ("a car at 15 m/s due East slows to 3 m/s due East" was
    drawn as two cars queued on a road, textbook round 2026-11-25)."""
    return any(
        _same_angle(one.angle, other.angle)
        and any(arrow.name is None and arrow.mass is None for arrow in (one, other))
        for at, one in enumerate(arrows)
        for other in arrows[at + 1 :]
    )


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
        if not all(mention.readable for mention in stated):
            return False
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
    owned = {start for starts in read.masses.values() for start in starts}
    for mass in read.stated.equal_to(written, "kg"):
        if mass.start in read.masses.get(body.start, []) and mass.start not in read.used_masses:
            read.used_masses.add(mass.start)
            return mass
        # Shared only when it is no body's own: the one mass stated, or one tied to none.
        alone = read.masses_stated == 1 or mass.start not in owned
        if alone and _SHARED.search(read.stated.sentence(mass)):
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
    if not all(mention.readable for mention in stated):
        return None, False  # its direction is unread ("a westerly", "north-north-east")
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
    label = label_of(" ".join(words))
    for found in re.finditer(pattern, text, re.IGNORECASE):
        named = tie(text, found.start(), found.end(), read.givens, label)
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
    return stick_together(Stated.of(question).text)
