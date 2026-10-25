"""Sentences in a reply that say Recall cannot keep reminders.

Live (2026-10-25): asked "what do you remember about me so far?", a reply listed the
reminder card offered earlier and went on "I can't set reminders from here, though, so
you'll want to set that one in your own reminder app." Recall sets them: a card the user
taps. ``without_denials`` drops those sentences and keeps the rest of the reply.

A denial says the assistant cannot set, add or keep a reminder or to-do, or sends the
user to another app to set one. "I can't remind you enough how much sleep matters", "I
can't read your iPhone's Reminders app" (true: Recall has its own list) and "set an
alarm in your clock app" are not denials.
"""

from __future__ import annotations

import re

from app.modules.todos.reply_claims import split_sentences
from app.services.md_fence_scan import line_fences
from app.services.text_normalize import straighten_apostrophes

_CANNOT = (
    r"\bi\s*(?:can't|cannot|can not|am not able to|'m not able to|am unable to|'m unable to"
    r"|don't have (?:the ability|a way) to|do not have (?:the ability|a way) to|have no way to)"
    r"\s+(?:actually\s+|directly\s+|really\s+|personally\s+)?"
)
_DENIAL = re.compile(
    "|".join(
        (
            rf"{_CANNOT}(?:set|create|make|add|schedule|save|keep|manage)\s+(?:up\s+)?"
            r"(?:any\s+|a\s+|an\s+|the\s+|that\s+|this\s+|your\s+|real\s+|actual\s+)?"
            r"(?:reminders?|to-?dos?|to-?do lists?|alarms? or reminders?)\b"
            r"(?!\s+(?:lists?\s+)?(?:app|apps|template|system)\b)",
            rf"{_CANNOT}remind you\b(?!\s+(?:enough|how|of|what|why)\b)",
            r"\byou(?:'ll| will)?\s*(?:want|need|have)\s+to\s+(?:set|add|put|create|save)\s+"
            r"(?:that|it|this|them|that one|this one)\s+(?:up\s+)?(?:yourself\s+)?in\s+"
            r"(?:your|a)\s+(?:own\s+|phone's\s+|separate\s+|regular\s+)?"
            r"(?:reminders?|to-?do|task)\s+(?:app|list)\b",
            r"\buse\s+(?:your|a)\s+(?:own\s+|phone's\s+|separate\s+)?(?:reminders?|to-?do)\s+app\s+"
            r"(?:for|to set)\b",
        )
    ),
    re.IGNORECASE,
)


def is_denial(sentence: str) -> bool:
    return bool(_DENIAL.search(straighten_apostrophes(sentence)))


def without_denials(text: str) -> str:
    """The reply without sentences saying reminders cannot be set here. Code stays."""
    if not _DENIAL.search(straighten_apostrophes(text)):
        return text
    kept: list[str] = []
    for line, fence in zip(text.split("\n"), line_fences(text), strict=True):
        if fence is not None:
            kept.append(line)
            continue
        sentences = split_sentences(line)
        left = [sentence for sentence in sentences if not is_denial(sentence)]
        if left == sentences:
            kept.append(line)
        elif left:
            kept.append(" ".join(left))
        # A line that was only the denial goes, and so does its list marker.
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return body or text
