"""How hard a turn should think: off, hard, or escalate.

Thinking costs time and output tokens, so an ordinary question gets none. A
genuinely hard question gets the cheapest level that thinks (``message_needs
_thinking``). One level more only when the user pushes back on the answer
before ("that's wrong", "try again", "that's not what I asked") or regenerates it. The
catalog turns each level into a value the model supports.

How hard a question is, is the turn's read's answer (``chat.turn_decision``'s effort)
when it answers in time (``chat.decided_turn``): the word rules (a length, a code fence,
trigger words, the subject lanes) gave a four-part word problem about four runners' speeds
no thinking (2026-11-09). With no answer, they still decide, here.
"""

from __future__ import annotations

import re

from app.core.config import Settings
from app.gateways.reasoning import EFFORTS, ThinkingLevel, thinking_value
from app.models import model_catalog
from app.modules.chat.model_routing.route import message_needs_thinking

# Pushback on the reply just given. Bare "wrong" is not enough: "what's wrong
# with my code" asks for help, it does not dispute an answer.
_DISPUTE = re.compile(
    r"\b(?:that(?:'s|\s+is|\s+was)|this\s+is|it(?:'s|\s+is)|you(?:'re|\s+are))\s+"
    r"(?:wrong|incorrect|not\s+(?:right|correct|it)|a\s+mistake|mistaken)\b"
    r"|\bwrong\s+answer\b|\b(?:the\s+)?answer\s+is\s+(?:wrong|incorrect)\b"
    r"|\byou\s+(?:made|have)\s+(?:a\s+)?(?:mistake|error)\b"
    r"|\bthere(?:'s|\s+is)\s+(?:a\s+)?(?:mistake|error)\s+in\s+(?:your|the)\s+(?:answer|working)\b"
    r"|\b(?:try|do\s+it|solve\s+it|check\s+it)\s+again\b|\bre-?check\b|\bdouble[- ]check\b"
    r"|\bare\s+you\s+sure\b|\bthat\s+can(?:'t|not)\s+be\s+right\b|\bnot\s+what\s+i\s+got\b"
    # The question itself was misread, or a correction was ignored: think again.
    # "No, I said I'm vegetarian" corrects a fact; it needs no more thought.
    r"|\b(?:that(?:'s|\s+is)|this\s+is|it(?:'s|\s+is))\s+not\s+what\s+i\s+"
    r"(?:asked|meant|said|wanted)\b|\byou\s+(?:misunderstood|misread)\b|\bi\s+already\s+told\s+you\b"
    # A bare "no" answers an offer ("Want a menu section?"); "wrong" disputes.
    r"|^\s*(?:incorrect|wrong)[\s,.!]*$",
    re.IGNORECASE,
)
_MAX_DISPUTE_CHARS = 240


def is_answer_dispute(text: str | None) -> bool:
    """True when a short message says the previous answer was wrong."""
    if not text:
        return False
    cleaned = " ".join(text.replace("\u2019", "'").split())
    return len(cleaned) <= _MAX_DISPUTE_CHARS and _DISPUTE.search(cleaned) is not None


def thinking_level(
    content: str,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
    lesson_active: bool = False,
    regenerate: bool = False,
    settings: Settings | None = None,
) -> ThinkingLevel:
    """The word rules' thinking level for this turn; escalation needs an answer to dispute."""
    if regenerate or (prior_user and is_answer_dispute(content)):
        return "escalate"
    hard = message_needs_thinking(
        content,
        prior_user=prior_user,
        prior_model=prior_model,
        lesson_active=lesson_active,
        settings=settings,
    )
    return "hard" if hard else "off"


def thinks_when_hard(alias: str) -> bool:
    """The model reasons at the "hard" level: its catalog names an effort for it."""
    value = thinking_value(model_catalog.get(alias), "hard")
    return value in EFFORTS and value != "none"


def lane_for_think(
    model: str, pool: list[str], unsteady: frozenset[str] = frozenset()
) -> str | None:
    """Auto's lane for a turn the read says to think on, when it is the maths lane and its
    model cannot think (GLM 5.2 sends no reasoning at "hard"): the pool's smart lane, or
    another of the pool's strong models that can think. None keeps the lane. A hard
    everyday question reaches the strong lane by the read's table (``ROUTING.decided``),
    not here. A model whose breaker is open or half-open (``unsteady``) is never moved to:
    the turn would wait out its timeout."""
    if model != model_catalog.auto_math_alias() or model not in pool or thinks_when_hard(model):
        return None
    smart = model_catalog.auto_smart_alias()
    strong = [
        m
        for m in pool
        if model_catalog.get(m).tier in {"smart", "max"} and m != model and m not in unsteady
    ]
    ordered = ([smart] if smart in strong else []) + [m for m in strong if m != smart]
    return next((alias for alias in ordered if thinks_when_hard(alias)), None)
