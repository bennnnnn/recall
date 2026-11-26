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


# The force each symbol of the server's picture stands for, read from what it says it shows
# ("its weight mg, the normal force N, the pull T and friction f against the motion").
_SHOWN: tuple[tuple[re.Pattern[str], Force], ...] = (
    (re.compile(r"\bweights?\b"), "weight"),
    (re.compile(r"\bnormal\b"), "normal"),
    (re.compile(r"\bfriction\b"), "friction"),
    (re.compile(r"\b(?:tension|pull)\b"), "tension"),
    (re.compile(r"\b(?:push|driving force)\b"), "push"),
    (re.compile(r"\bair resistance\b"), "drag"),
)


def _shown(shows: str) -> set[Force]:
    return {force for pattern, force in _SHOWN if pattern.search(shows.lower())}


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
    if _shown(picture.shows) != set(described.forces):
        logger.info("described forces not drawn: the server reads other forces")
        return []
    return [picture.spec]
