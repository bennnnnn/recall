"""Auto routing's physics lane: verified physics stays fast, uncovered homework goes smart.

Physics' read of a line for model routing (chat's ``model_routing/route``), asked through
its adapter (``services/subjects/registry``). ``_physics_solves`` is a reading
(``core/readings.py``): the turn reads it in the SymPy pool with the rest of its message,
so routing never runs the physics solver on the event loop.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from app.core.readings import reading

logger = logging.getLogger(__name__)

# Homework physics the verified solver does not cover (incline, momentum,
# escape velocity, …). needs_symbolic stays the solver gate so we don't
# inject fake verified fences; Auto still escalates so a weak model isn't
# left to invent F=ma on an incline. Bare "physics" must not match.
#
# Deliberately a separate list from `modules.physics.registry.PHYSICS_CUES` /
# `has_supported_physics_cue`, not a duplicate of it: that one gates "the
# solver's extractors might handle this text," which has grown to twenty
# kinds. This one gates "escalate Auto to the smarter model," which some
# entries here now overlap with a covered kind (momentum, simple harmonic,
# centripetal) — kept anyway, since a smarter model's surrounding
# explanation is still worth it even when the number itself is guaranteed.
# If that stops being true for a given phrase, prune it here; don't point
# this at `has_supported_physics_cue` — inverting the gate would escalate
# exactly the questions the solver already has covered, and stop escalating
# the ones it doesn't, which is backwards from this function's purpose.
_PHYSICS_HOMEWORK_CUES = (
    "frictionless",
    "incline",
    "inclined plane",
    "momentum",
    "escape velocity",
    "centripetal",
    "simple harmonic",
    "coefficient of friction",
    "normal force",
    "pendulum",
    "projectile motion",
    "free body",
    "atwood",
)
# Formula / conceptual asks that are hard even without a printed number.
_PHYSICS_FORMULA_CUES = (
    "escape velocity",
    "simple harmonic",
    "pendulum",
    "atwood",
    "projectile motion",
)


def _cue_pattern(cues: tuple[str, ...]) -> re.Pattern[str]:
    """Any cue as a word of its own, or with a plural or past ending ("inclined",
    "pendulums"): never inside another word, as "incline" is in "disinclined"."""
    words = "|".join(re.escape(cue) for cue in cues)
    return re.compile(rf"\b(?:{words})(?:s|d)?\b")


_HOMEWORK_CUE = _cue_pattern(_PHYSICS_HOMEWORK_CUES)
_FORMULA_CUE = _cue_pattern(_PHYSICS_FORMULA_CUES)


def _looks_like_physics_homework(content: str) -> bool:
    """Hard physics asks the solver templates don't cover.

    Requires a quantity (a digit) for everyday words like "momentum", so
    "the project has momentum" stays on the fast model. Formula phrases
    (escape velocity, pendulum, …) escalate even without a number.
    """
    lower = content.lower()
    if _HOMEWORK_CUE.search(lower) is None:
        return False
    if any(ch.isdigit() for ch in content):
        return True
    return _FORMULA_CUE.search(lower) is not None


@reading(declined=False)
@lru_cache(maxsize=128)
def _physics_solves(content: str) -> bool:
    """Whether the verified solver answers this line: a question in lettered parts the
    template answers one of ("the speed with no friction", then "the maximum speed" with
    it) is the strong model's (2026-11-16).

    Routing asks this of the current line and again of a prior one, every turn; the
    answer only depends on the text. Any failure is a decline: the strong model answers
    it, and the turn never fails for a routing hint.
    """
    from app.core.config import get_settings
    from app.modules.physics.prompt import solve_physics_request

    try:
        outcome, block = solve_physics_request(content, get_settings(), True)
    except Exception:
        logger.warning("physics routing solve failed", exc_info=True)
        return False
    if outcome != "verified" or block is None:
        return False
    from app.services.question_parts import labelled_parts

    # Only a question in lettered parts the solve leaves some of: a message whose other ask
    # is the weather or a café nearby keeps the fast model for its physics.
    return not (block.partial and labelled_parts(content) >= 2)


def physics_fast_lane(content: str, *, tools_on: bool, claimed: bool = False) -> bool | None:
    """Verified physics stays on the fast model (True). Uncovered homework goes to the
    strong one (False). None when the line is no physics.

    The fast tier is only for a template the solver actually finishes, and only while
    math tools are on. Otherwise the strong model answers it. A line the subject order
    gave physics (``claimed``) is homework when physics reads a problem in it or it asks in
    lettered parts: "a ball launched at 15 m/s … from the bottom of a hill that slopes at
    20°. (a) … (b) …" went to the everyday model, thinking off, when the turn's read was
    late, and its range came back 26.0 m for 16.7 m (2026-11-16).
    """
    from app.modules.physics import extract_physics_intent, needs_physics
    from app.services.question_parts import labelled_parts

    cues = _looks_like_physics_homework(content)
    # The guard first: a line no physics cue or claim names is never extracted (Gemini on
    # #2489; each read is a turn reading, answered in the pool, all the same).
    if not (cues or claimed or needs_physics(content)):
        return None
    intent = extract_physics_intent(content)
    # A line the order claims is homework when physics reads a problem in it, or it asks
    # in lettered parts: "a drive to the airport" or "my battery went from 100% to 25%"
    # stays on the everyday model.
    homework = cues or (claimed and (intent is not None or labelled_parts(content) >= 2))
    if not homework and not needs_physics(content):
        return None
    if intent is None:
        return False if homework else None
    return tools_on and _physics_solves(content)
