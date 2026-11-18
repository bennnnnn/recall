"""The physics readers' own reading of a question's setup, which a described scene must
agree with.

``extract_physics_intent`` is the reader the solvers and the STEM sweep trust: it reads a
launch's height and direction, a collision's type and which body moves, the media a ray
passes between, the planet an orbit goes round. A question in parts is read part by part
as its solve reads it (``split_parts.part_readings``). A scene is drawn only from one of
these readings; a setup no reader reads is not drawn.
"""

from __future__ import annotations

from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.split_parts import part_readings

# Readings at most: a question in eight parts is read twice per part.
_MAX_READINGS = 17


def setup_readings(text: str) -> list[PhysicsIntent]:
    """The readings of ``text`` the physics reader makes: the whole question, then each
    of its parts."""
    readings: list[PhysicsIntent] = []
    for reading in [text, *part_readings(text)][:_MAX_READINGS]:
        intent = extract_physics_intent(reading)
        if intent is not None and intent.physics_op:
            readings.append(intent)
    return readings
