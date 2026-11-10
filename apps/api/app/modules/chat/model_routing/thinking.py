"""How hard a turn should think: off, hard, or escalate.

Thinking costs time and output tokens, so an ordinary question gets none. A
genuinely hard question gets the cheapest level that thinks (``message_needs
_thinking``). One level more only when the user pushes back on the answer
before ("that's wrong", "try again", "that's not what I asked") or regenerates it. The
catalog turns each level into a value the model supports.

Whether a question is hard is the turn's read's answer (``web_search.live_read``'s
``think``) when it answers in time: the word rules (a length, a code fence, trigger words,
the subject lanes) gave a four-part word problem about four runners' speeds no thinking
(2026-11-09). With no answer, they still decide.
"""

from __future__ import annotations

import re

from app.core.config import Settings
from app.gateways.reasoning import ThinkingLevel
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
    read_think: bool | None = None,
) -> ThinkingLevel:
    """The thinking level for this turn; escalation needs an answer to dispute.
    ``read_think``: the turn's read said whether to think; None, it gave no answer."""
    if regenerate or (prior_user and is_answer_dispute(content)):
        return "escalate"
    if read_think is not None:
        return with_read(read_think)
    hard = message_needs_thinking(
        content,
        prior_user=prior_user,
        prior_model=prior_model,
        lesson_active=lesson_active,
        settings=settings,
    )
    return "hard" if hard else "off"


def with_read(read_think: bool, level: ThinkingLevel | bool | str = "off") -> ThinkingLevel:
    """The level once the read has answered: a turn already escalated stays so."""
    if level == "escalate":
        return "escalate"
    return "hard" if read_think else "off"
