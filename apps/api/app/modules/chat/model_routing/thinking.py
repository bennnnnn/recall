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


def thinks_on_escalate(alias: str) -> bool:
    """The model reasons at the "escalate" level: its catalog names an effort for it."""
    value = thinking_value(model_catalog.get(alias), "escalate")
    return value in EFFORTS and value != "none"


def escalation_model(
    model: str,
    plan_lane: tuple[str, ...],
    pool: list[str],
    unsteady: frozenset[str] = frozenset(),
) -> str:
    """The model a regenerate runs on: ``model`` when it thinks at the escalate level (Pro's
    everyday model, the maths lane on a paid plan), else the plan's model that does. A
    regenerate asks one level more (``thinking_level``), and the cheap everyday model sends
    no reasoning at any level, so "try again" on it repeated the same call (2026-11-13).

    The plan's thinking model is the first of its maths lane and that lane's backup
    (billing's ``math_lane_for``) that thinks: DeepSeek on a plan that has it, GLM 5.3
    Flash behind Qwen3.7 Flash on Free. With neither usable (switched off, or its breaker
    open or half-open: ``unsteady``), the cheapest of the pool that thinks; with none,
    ``model``."""
    if model not in model_catalog.known_ids() or thinks_on_escalate(model):
        return model
    usable = [alias for alias in pool if alias not in unsteady]
    thinking = [alias for alias in usable if thinks_on_escalate(alias)]
    chosen = next((alias for alias in plan_lane if alias in thinking), None)
    if chosen is None and thinking:
        chosen = min(
            thinking, key=lambda alias: model_catalog.price_sort_key(model_catalog.get(alias))
        )
    return chosen or model
