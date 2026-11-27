"""The forces on one body, as a figure read names them, drawn only when the server reads the
same forces.

"A box is pulled along a flat table ... Work out the coefficient of kinetic friction" asks to
see nothing, yet the textbook draws its free-body diagram, and so must a reply (owner,
2026-11-25: "Diagrams must be drawn"). The figure read says which body and which forces:

    {"kind": "forces", "body": "box", "forces": ["weight", "normal", "tension", "friction"]}

The server reads the situation itself (``physics.force_pictures``: a slope, a level surface,
a rope, a push, a hanging body, a body in the air, a pulley rig, a curve) and draws its own
free-body diagram only when the forces it reads are exactly the ones named: two readings that
agree. A ball "held on a slope ... let go" reads as held still to the server and sliding to
the read, so nothing is drawn. A body the server does not draw (a ladder against a wall), or a
force either reading lacks, draws nothing.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.physics.force_pictures import force_picture
from app.modules.physics.schemas import SimulationBlockSpec

logger = logging.getLogger(__name__)

Force = Literal["weight", "normal", "friction", "tension", "push", "drag"]


class _Forces(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["forces"]
    body: str = Field(max_length=30)
    forces: list[Force] = Field(min_length=1, max_length=6)
    part: str | None = None


# The force each arrow of the server's picture is, by its label or its derived kind: the
# forces drawn, never the words around them (a held block's "(friction acts along the slope,
# whichever way keeps the block still)" draws no friction arrow; review of #2603).
_LABELS: dict[str, Force] = {
    "mg": "weight",
    "m₁g": "weight",
    "m₂g": "weight",
    "N": "normal",
    "f": "friction",
    "T": "tension",
    "F": "push",
    "drag": "drag",
}
_KINDS: dict[str, Force] = {"gravity": "weight", "normal": "normal", "friction": "friction"}
# One arrow that is two forces: a vehicle's "friction and air resistance f backward".
_FRICTION_AND_AIR = "friction and air resistance"


def _drawn(spec: SimulationBlockSpec) -> set[Force] | None:
    """The forces the picture draws, or None when an arrow is none the vocabulary names (a
    picture this check cannot read is drawn by nothing)."""
    forces: set[Force] = set()
    for vector in spec.vectors:
        if vector.role == "motion":
            continue  # an acceleration, never a force
        force = _LABELS.get((vector.label or "").strip())
        if force is None:
            return None
        forces.add(force)
    for arrow in spec.arrows:
        if arrow in _KINDS:
            forces.add(_KINDS[arrow])
    return forces


def _names_body(question: str, body: str) -> bool:
    """The question names the body as the read wrote it, as a word (one or many)."""
    word = re.escape(body.strip().lower())
    return bool(word) and re.search(rf"\b{word}(?:e?s)?\b", question.lower()) is not None


def described_forces(body: str, texts: Sequence[str]) -> list[SimulationBlockSpec]:
    """The free-body diagram one block describes, as the server draws it; none when it is
    no forces block or the server reads other forces than it names (``texts[0]``: the
    problem)."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, dict) or data.get("kind") != "forces":
        return []
    try:
        described = _Forces.model_validate(data)
    except ValidationError as exc:
        logger.info("described forces not read: %s", exc.errors()[0].get("loc"))
        return []
    question = texts[0] if texts else ""
    if not _names_body(question, described.body):
        logger.info("described forces not drawn: the question names no such body")
        return []
    picture = force_picture(question, asked=False)
    if picture is None:
        logger.info("described forces not drawn: no situation the server draws")
        return []
    drawn = _drawn(picture.spec)
    if drawn is None or not _agree(drawn, set(described.forces), picture.shows):
        logger.info("described forces not drawn: the server reads other forces")
        return []
    return [picture.spec]


# Forces every body on a surface has, which a read that names only the ones along the motion
# ("a driving force of 25 kN and friction of 10 kN" on a lorry) leaves unsaid.
_ALWAYS = frozenset({"weight", "normal"})


def _agree(server: set[Force], read: set[Force], shows: str) -> bool:
    """Every force the read names is one the server draws, and every one the server adds is
    a weight or a normal force, or air resistance drawn in one arrow with friction ("friction
    and air resistance f backward"). A force only the server reads (friction on a ball "held"
    on a slope, then let go) is a disagreement, and draws nothing."""
    # A read that names air resistance beside friction agrees with the vehicle's one arrow
    # that is both.
    if _FRICTION_AND_AIR in shows and "friction" in server:
        server = server | {"drag"}
        if "friction" in read:
            read = read | {"drag"}
    extra = server - read
    return read <= server and extra <= _ALWAYS
