"""The answer the server's own solver gives a model's read.

A read (``service.read_with_model``) is a checked intent, never a number. Each subject's
solver turns it into the same answer card a pattern read would get; a second opinion on a
reply (``chat.second_opinion``) and the reader's measurement (``reader_eval``) both read
it here. Run in the SymPy pool: maths and chemistry solve with SymPy.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.modules.chemistry.model_read import read_answer as chemistry_answer
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.math.schemas import MathIntent
from app.modules.math.tools.llm_extract import read_answer as math_answer
from app.modules.model_reader.schemas import ModelRead
from app.modules.physics.model_read import read_answer as physics_answer
from app.modules.physics.schemas import PhysicsIntent

logger = logging.getLogger(__name__)


def solved_read(subject: str | None, intent: object, settings: Settings) -> str | None:
    """The answer card for a read's ``intent``, or None when its subject's solver gives
    none or fails."""
    try:
        if subject == "physics" and isinstance(intent, PhysicsIntent):
            return physics_answer(intent, settings)
        if subject == "chemistry" and isinstance(intent, ChemistryIntent):
            return chemistry_answer(intent)
        if subject == "math" and isinstance(intent, MathIntent):
            return math_answer(intent, settings)
    except Exception as exc:
        logger.info("solving a model read failed (%s)", type(exc).__name__)
    return None


def read_card(read: ModelRead, settings: Settings) -> str | None:
    """The answer card for a finished read, or None when it has no intent."""
    if read.reason != "ok" or read.intent is None:
        return None
    return solved_read(read.subject, read.intent, settings)
