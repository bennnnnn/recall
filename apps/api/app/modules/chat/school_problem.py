"""Whether the chat before a message holds a maths, physics or chemistry problem.

A request to see "it" is a subject's to draw only when the chat holds a problem a subject
could draw. An everyday chat holds none, so neither the prep nor the turn's read waits on
a model for it (review, 2026-11-22): "show me a picture of it" after the Colosseum is a
photo's, and "can u show me a picture" after a chat about dinner a painting's.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.core.config import Settings
from app.services.md_fence_scan import iter_fences

logger = logging.getLogger(__name__)

# The cards the app writes for a problem it worked or drew: a checked answer, a worked
# layout, a curve, a figure, a scene, a molecule.
_PROBLEM_CARDS = frozenset(
    {"answer", "worked", "graph", "geometry", "simulation", "smiles", "molecule3d", "chemistry"}
)


def answers_a_problem(reply: str) -> bool:
    """The app's reply carries a card of a problem it worked or drew: "7 notebooks at $2
    each" reads as no subject's question, but its reply's answer card says it was one."""
    return any(fence.lang in _PROBLEM_CARDS for fence in iter_fences(reply))


def holds_a_school_problem(lines: Sequence[str]) -> bool:
    """Some line is a maths, physics or chemistry question, as the subject readers read
    it. Runs in the SymPy pool."""
    from app.modules.chat.turn_prep.reading import subject_of

    return any(subject_of(line) is not None for line in lines if line.strip())


async def chat_holds_a_school_problem(
    settings: Settings, lines: Sequence[str], replies: Sequence[str] = ()
) -> bool:
    """A reply of ``replies`` answers a problem, or ``holds_a_school_problem`` of the user's
    ``lines`` in the pool; no when the pool gave up (the turn's own readings stand: this is
    no reading of the turn's message)."""
    from app.core.sympy_executor import run_sympy

    if any(answers_a_problem(reply) for reply in replies):
        return True
    if not any(line.strip() for line in lines):
        return False
    try:
        return await run_sympy(
            holds_a_school_problem,
            list(lines),
            timeout=settings.subject_read_timeout_seconds,
            lane="reading",
        )
    except Exception as exc:  # A read that fails is no problem found: nothing waits.
        logger.info("school problem not read (%s)", type(exc).__name__)
        return False
