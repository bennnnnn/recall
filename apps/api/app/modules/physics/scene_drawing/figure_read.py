"""The picture a physics question is taught from, read beside the reply and drawn by the server.

A Grade 11 textbook round (2026-11-25) put 150 questions to the app; 77 needed a picture (the
forces on a box on a ramp, two displacements head to tail, a bar with its moments, a
projectile's path) and 11 got one. The reply was asked to describe its setup in a ```draw
block, and the fast reply models mostly left it out; nothing else drew a picture the student
had not asked for. The owner (2026-11-25): "Diagrams must be drawn".

So, as maths does (``math.figure.read``), one short structured call beside the reply says
what the question's picture is, in the blocks a physics reply describes (``contract``): a
scene, the question's own arrows, the forces on one body, a bar's moments, a motion's graph
and, asked for, an electric field. The server holds the block to the question exactly as it
holds a reply's (``build.physics_fences``): every value one the question states, every force
the server's own reading of the situation, every stated value of the picture's kind drawn.
One that does not hold draws nothing, and no picture ever waits for the reply's first word
(``chat.figure_turn`` adds it under the reply when it is done). Nothing here raises into a
turn.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.core import sympy_executor
from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.physics.field_lines.contract import FIELD_DRAW_CONTRACT
from app.modules.physics.scene_drawing.contract import (
    BEAM_VOCABULARY,
    FORCES_VOCABULARY,
    MOTION_DRAW_CONTRACT,
    SCENE_VOCABULARY,
    VECTORS_DRAW_CONTRACT,
)

logger = logging.getLogger(__name__)

_MAX_TOKENS = 700
# A question in many parts states its last pictures late ("8. Graphs: ..."): read it whole.
_MAX_CHARS = 4000
_EARLIER_CHARS = 600
# The most pictures one question gets: its setup and its motion's graphs.
_MOST_BLOCKS = 3


class PhysicsPictureRead(BaseModel):
    """The block that draws the question's picture, the blocks of the pictures it asks for
    (its free-body diagram and its motion's graphs), or none."""

    draw: dict[str, Any] | list[dict[str, Any]] | None = None


_ASKED = (
    "The user wants to see a picture for this physics question. Say what it shows as one "
    "block below, from what the question states; a question that asks for several pictures "
    "(a free-body diagram and its motion's graphs) gets a block for each.\n"
)
# Not asked: the picture a textbook draws beside the problem (owner, 2026-11-25).
_TEACH = (
    "The user did not ask for a picture, but a textbook draws one beside nearly every "
    "problem about a physical situation, and so do you: whenever the question describes "
    "a body and the forces on it, a body on a slope or pulled along a floor, displacements, "
    "velocities or forces with their directions (a journey in legs, bodies heading for a "
    "junction, forces on one point), a projectile, a collision, a pendulum, a bar with "
    "forces along it or a motion in stages, give the block that shows it. draw is null "
    "only for a question with no physical situation (a definition, a law or an idea in "
    "words, a unit conversion, a formula to rearrange) or one no block below can show (a "
    "circuit, a wave, heat flowing, a fluid in a pipe).\n"
)
_RULES = (
    'Answer only JSON: {"draw": <one block>}, {"draw": [<a block for each picture asked, '
    'in the order asked>]} or {"draw": null}. Each block is the JSON '
    "named below (a reply writes it in a ```draw block; here it is the value of draw). "
    "Copy every value exactly as the question writes it, with its unit; never a value you "
    "worked out, never a coordinate. Draw what the question describes, at the moment it "
    "describes it. Never guess a value, a direction or a force the question does not give: "
    "a block that would need one is null, as no picture is better than a wrong one.\n"
    "When the last message only asks to draw or show it, the picture is the problem in the "
    "earlier user messages.\n"
    "A body at rest, held or in limiting equilibrium on a slope, or pulled or pushed along "
    "a surface, is forces; the incline scene is a block sliding down with a stated "
    "coefficient of friction. Arrows of one quantity the question gives directions are "
    "vectors. A bar with forces at points along it is beam.\n"
    'Examples: "A box is pulled along a flat table with a force of 7 N. Its mass is 2 kg. '
    'Find the coefficient of kinetic friction." -> {"draw": {"kind": "forces", "body": '
    '"box", "forces": ["weight", "normal", "tension", "friction"]}}; "A crate weighing '
    '40 N rests on a ramp at 25°." -> {"draw": {"kind": "forces", "body": "crate", '
    '"forces": ["weight", "normal", "friction"]}}; "A cyclist rides 4 km due south then 3 '
    'km due west. Find the displacement." -> {"draw": {"kind": "vectors", "layout": '
    '"chain", "quantity": "displacement", "arrows": [{"size": "4 km", "direction": "due '
    'south"}, {"size": "3 km", "direction": "due west"}], "resultant": true}}; "What is '
    'Newton\'s first law?" -> {"draw": null}; "Convert 72 km/h to m/s." -> {"draw": '
    "null}.\n\n"
)


def _prompt(asked: bool) -> str:
    blocks = [
        "A scene: " + SCENE_VOCABULARY,
        VECTORS_DRAW_CONTRACT,
        FORCES_VOCABULARY,
        BEAM_VOCABULARY,
        MOTION_DRAW_CONTRACT,
    ]
    if asked:
        blocks.append(FIELD_DRAW_CONTRACT)
    return (_ASKED if asked else _TEACH) + _RULES + "\n\n".join(blocks)


def _message(question: str, earlier: Sequence[str]) -> str:
    before = [text[:_EARLIER_CHARS] for text in earlier if text.strip()]
    if not before:
        return question[:_MAX_CHARS]
    joined = "\n".join(f"- {text}" for text in before)
    return f"Earlier user messages:\n{joined}\n\nLast message: {question[:_MAX_CHARS]}"


async def read_physics_picture(
    settings: Settings, question: str, earlier: Sequence[str], *, asked: bool
) -> list[dict[str, Any]]:
    """The blocks the question's pictures are, as the figure read says them; none for none."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return []
        read = await complete_structured(
            settings=settings,
            # The lane that reads a physics question beside the reply (the formal reader's):
            # the maths figure read's model left the forces on a box on a ramp undrawn.
            model_alias=ROUTING.physics_setup,
            messages=[
                {"role": "system", "content": _prompt(asked)},
                {"role": "user", "content": _message(question, earlier)},
            ],
            schema=PhysicsPictureRead,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.figure_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure draws nothing.
        logger.info("physics figure read failed (%s)", type(exc).__name__)
        return []
    return _blocks(read.draw) if read is not None else []


def _blocks(draw: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """The read's blocks, in its order: none for null or a block of no kind."""
    blocks = [draw] if isinstance(draw, dict) else list(draw or [])
    drawn = [block for block in blocks if block.get("kind") not in (None, "none")]
    return drawn[:_MOST_BLOCKS]


# A scene's flags, which the read now and then writes among its values.
_FLAGS = ("sticks", "elastic", "horizontal", "components")


def normalized(block: dict[str, Any]) -> dict[str, Any]:
    """The read's block in the form a reply writes it: a scene named as its kind
    ({"kind": "banked_curve", "angle": "10°"}) is that scene with those values, and a flag
    written among the values ("horizontal": true) is the scene's own. Only the form changes:
    every value is still held to the question."""
    from app.modules.physics.scene_drawing.kinds import SCENES

    kind = block.get("kind")
    if isinstance(kind, str) and kind in SCENES:
        rest = {key: value for key, value in block.items() if key != "kind"}
        block = {"kind": "scene", "scene": kind, "values": rest}
    values = block.get("values")
    if block.get("kind") != "scene" or not isinstance(values, dict):
        return block
    flags = {key: values[key] for key in _FLAGS if isinstance(values.get(key), bool)}
    kept = {key: value for key, value in values.items() if key not in flags}
    return {**block, **flags, "values": kept}


def problem_text(question: str, earlier: Sequence[str]) -> str:
    """The text the picture's values are held to: the message alone, or on a follow-up the
    problem it follows and every message since, the message last ("A 2 kg box rests on a 30°
    ramp" then "What if the mass is 5 kg?" holds the box and its slope; review of #2603).
    ``earlier`` is the problem's messages, oldest first, and empty for a message that stands
    alone (``chat.figure_turn``)."""
    lines = [text for text in earlier if text.strip()]
    return "\n".join([*lines, question]) if lines else question


async def draw_physics_figure(
    question: str, earlier: Sequence[str], settings: Settings, *, asked: bool = True
) -> str | None:
    """The fence of the question's picture, read and checked; None when nothing is drawn.
    ``earlier``: the problem's earlier messages, oldest first."""
    from app.modules.physics.scene_drawing.build import physics_fences

    if not settings.figure_read_enabled or not question.strip():
        return None
    if not asked and not settings.teaching_figures_enabled:
        return None
    blocks = await read_physics_picture(settings, question, earlier, asked=asked)
    if not blocks:
        return None
    texts = [problem_text(question, earlier), question]
    try:
        fences = await sympy_executor.run_sympy(
            physics_fences,
            [json.dumps(normalized(block)) for block in blocks],
            texts,
            None,
            True,
            timeout=settings.stem_solve_timeout_seconds,
        )
    except Exception as exc:  # A failed build draws nothing; the reply stands.
        logger.info("physics figure build failed (%s)", type(exc).__name__)
        return None
    kinds = ",".join(str(b.get("of") or b.get("scene") or b["kind"]) for b in blocks)
    way = "asked" if asked else "teach"
    logger.info("physics figure %s: %s -> %d drawn", way, kinds, len(fences))
    return "\n\n".join(fences) if fences else None
