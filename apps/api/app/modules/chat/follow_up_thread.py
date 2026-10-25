"""Which subject problem a line follows up on.

"Why do we divide distance by time?" names no subject itself; it belongs to the bike
problem a line or two back. Any question within three user lines continues the problem,
as long as its reply still works it (``follow_up_ground``): live (2026-10-25), "cool. i'm
going to lisbon next month for 4 days, what should i not miss?" two lines after a
rectangle problem got "What if perimeter was 48 cm?" under its travel tips. Each turn is
judged by its own reply, so a remark or a new topic in between does not cut a later
follow-up off. A read of the user's own to-do list follows up on nothing
(``related_questions``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.modules.chat.continuation_subject import (
    BIOLOGY_CUES,
    is_new_problem_request,
    is_pure_continuation,
)
from app.modules.chat.follow_up_ground import works_the_problem
from app.modules.chat.prompt_constants.routing import is_lightweight_chat_turn
from app.services.problem_followup import message_role_content
from app.services.subject_solving import detect_subject
from app.services.text_normalize import collapse_ws

# A follow-up ("why?") belongs to a problem a few user lines back; further is stale.
_THREAD_USER_TURNS = 3
_FOLLOW_UP_LEADS = frozenset(
    {
        "why",
        "how",
        "what",
        "when",
        "where",
        "which",
        "can",
        "could",
        "is",
        "are",
        "does",
        "do",
        "explain",
        "show",
        "give",
        "try",
        "solve",
        "find",
        "and",
        "but",
        "so",
        "if",
    }
)


def subject_for_related(text: str) -> str | None:
    """Math, physics, chemistry, or biology. Anything else is skipped."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return None
    detected = detect_subject(cleaned)
    if detected is not None:
        return detected
    lowered = cleaned.casefold()
    if any(cue in lowered for cue in BIOLOGY_CUES):
        return "biology"
    return None


def _continues_thread(text: str) -> bool:
    """A question or a "one more" about the open problem, not small talk."""
    cleaned = collapse_ws(text)
    if not cleaned or is_lightweight_chat_turn(cleaned):
        return False
    if is_pure_continuation(cleaned) or is_new_problem_request(cleaned):
        return True
    words = cleaned.casefold().split()
    return cleaned.endswith("?") or (bool(words) and words[0].strip(",.") in _FOLLOW_UP_LEADS)


def thread_problem(
    question: str, prior: Sequence[Any] | None, answer: str | None = None
) -> str | None:
    """The subject problem this line follows up on, or None.

    "Why do we divide distance by time?" names no subject itself, so the
    follow-ups would stop after the first tapped "why". It still belongs to
    the bike problem two lines back. Given the turn's ``answer``, the reply
    must still work the problem: travel tips under a Lisbon question do not.
    """
    if subject_for_related(question) is not None:
        return question
    if not prior or not _continues_thread(question):
        return None
    users = 0
    reply: str | None = None
    for message in reversed(prior):
        role, content = message_role_content(message)
        if not content or not content.strip():
            continue
        if role == "assistant":
            reply = content
        if role != "user":
            continue
        users += 1
        if users > _THREAD_USER_TURNS:
            return None
        if subject_for_related(content) is not None:
            if answer is None or works_the_problem(content, reply, f"{question}\n{answer}"):
                return content
            return None
        # The reply seen so far answered this line, not an earlier one.
        reply = None
    return None
