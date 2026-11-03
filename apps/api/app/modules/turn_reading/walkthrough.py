"""Whether a message asks for a walkthrough ("help me understand two sum", "walk me
through recursion", "I don't understand pointers"): one idea explained in full now,
not a course and not a task to carry out."""

from __future__ import annotations

import re

from app.modules.turn_reading.stuck import names_a_thing, stuck_on_a_topic, stuck_topic
from app.modules.turn_reading.teaching import PROCEDURE
from app.services.text_normalize import collapse_ws, straighten_apostrophes

# Paperwork is a task: steps to take, nothing to practise ("walk me through the visa
# requirements for Kenya", "the paperwork for renting an apartment"). Only as a phrase:
# the bare words name subjects too ("requirements.txt", "requirements engineering", "a
# permit system in Django").
_PAPERWORK = re.compile(
    r"\bpaperwork\b"
    r"|\b(?:visa|passport|residency|residence|immigration|entry|travel|customs|tax|"
    r"work|building|parking)\s+(?:requirements?|applications?|forms?|process|permits?)\b"
    r"|\b(?:visas?|permits?|licen[cs]es?)\s+(?:requirements?|applications?|forms?|process)\b"
    r"|\bapply(?:ing)?\s+for\s+(?:a\s+|an\s+)?(?:\w+\s+)?(?:visa|permit|passport|licen[cs]e)\b",
    re.IGNORECASE,
)


# "Help me understand two sum", or stuck on a topic ("I don't understand recursion",
# stuck.py): one idea, explained in full now, building to the answer in one reply.
# Not a subject: the last reply, something of the user's own or someone's ("break down my
# budget", "walk me through your reasoning"), or an event ("help me understand what happened").
_WALKTHROUGH = re.compile(
    r"(?:\bhelp\s+me\s+understand|\bwalk\s+me\s+through|\bbreak\s+down)\s+"
    r"(?!(?:it|this|that|these|those|you|your|my|our|his|her|their|its|why|who|when|where|"
    r"what\s+(?:happened|you|i|he|she|they|we|it))\b)[^\W\d_]"
    r"|\bexplain\b[^.?!\n]{1,80}\bstep[- ]by[- ]step\b",
    re.IGNORECASE,
)


# "Walk me through changing a tire" / "how to set up Docker step by step" is a
# task to do: it keeps the numbered how-to steps.
_TASK_OBJECT = re.compile(r"\b(?:how\s+(?:to|do\s+i|can\s+i)|[a-z]{3,}ing)\b", re.IGNORECASE)


def is_walkthrough_request(text: str) -> bool:
    """True for "help me understand X" / "walk me through X": a full explanation now."""
    cleaned = straighten_apostrophes(collapse_ws(text))
    if not cleaned or len(cleaned) > 400:
        return False
    match = _WALKTHROUGH.search(cleaned)
    if match is None:
        return stuck_on_a_topic(cleaned) and not _is_a_task(cleaned)
    rest = cleaned[match.start() :]
    if names_a_thing(cleaned[match.end() - 1 :]):
        return False
    first_object = rest.split()[3:4] if rest.lower().startswith("walk me through") else []
    if first_object and _TASK_OBJECT.fullmatch(first_object[0]):
        return False
    return not (_is_a_task(cleaned) or re.search(r"\bhow\s+(?:to|do\s+i)\b", rest, re.I))


def _is_a_task(cleaned: str) -> bool:
    return bool(PROCEDURE.search(cleaned) or _PAPERWORK.search(cleaned))


def walkthrough_topic(text: str) -> str | None:
    """The words from a walkthrough's topic on ("walk me through two sum" -> "two sum");
    None when ``text`` is no walkthrough. The caller ends the topic."""
    cleaned = straighten_apostrophes(collapse_ws(text))
    if not is_walkthrough_request(cleaned):
        return None
    match = _WALKTHROUGH.search(cleaned)
    if match is None:
        return stuck_topic(cleaned)
    if match.group(0).lower().startswith("explain"):
        return re.sub(r"(?i)^explain\s+", "", match.group(0))
    return cleaned[match.end() - 1 :]
