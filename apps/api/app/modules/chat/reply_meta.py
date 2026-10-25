"""Sentences a reply says about the turn rather than to the user.

Live chat (2026-10-25): "1" and "Okay." were answered "Got it. It's currently Sunday,
October 25, 2026, 6:15 PM EDT." The prompt gives every reply the clock, and a short turn
read it back as filler. A sentence that opens with today's full date goes when the
user's message is not about a time, a day or a date. A yes to an offer was answered
"Dev, you accepted my offer, so here is…": the lead-in about the yes goes, the offer stays.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import line_fences
from app.services.text_normalize import straighten_apostrophes

_WEEKDAY = r"(?:mon|tues|wednes|thurs|fri|satur|sun)day"
_MONTH = (
    r"(?:january|february|march|april|may|june|july|august|september|october|november|"
    r"december)"
)
# "It's currently Sunday, October 25, 2026, 6:15 PM EDT…": the prompt's clock, read back.
_CLOCK_SENTENCE = re.compile(
    rf"^\W*it(?:'s|\s+is)\s+(?:currently\s+|now\s+)?[*_]*{_WEEKDAY},\s+{_MONTH}\s+\d{{1,2}},\s+\d{{4}}\b",
    re.IGNORECASE,
)
# The user's message is about time: the date may well be the answer.
_ABOUT_TIME = re.compile(
    rf"\b(?:time|date|day|days|today|tonight|tomorrow|yesterday|week|weekend|month|year|"
    rf"clock|calendar|now|{_WEEKDAY}|{_MONTH})\b",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
# "Dev, you accepted my offer, so here is…", "You accepted my last offer again, so…".
_ACCEPTED_LEAD = re.compile(
    r"^(?:[A-Z][\w'-]*,\s+)?you(?:'ve|\s+have)?\s+accepted\s+my\s+(?:last\s+)?offer"
    r"(?:\s+again)?\s*[,.]\s*(?:so\s+)?",
    re.IGNORECASE,
)


def _without_clock(line: str) -> str | None:
    sentences = _SENTENCE_BREAK.split(line)
    kept = [part for part in sentences if not _CLOCK_SENTENCE.match(straighten_apostrophes(part))]
    if kept == sentences:
        return line
    joined = " ".join(kept).strip()
    return joined or None


def without_turn_meta(text: str, asked: str) -> str:
    """The reply without an unasked clock sentence or a lead-in about an accepted offer."""
    stripped = text.lstrip()
    lead = _ACCEPTED_LEAD.match(straighten_apostrophes(stripped))
    if lead is not None and lead.end() < len(stripped):
        rest = stripped[lead.end() :]
        text = rest[0].upper() + rest[1:]
    if _ABOUT_TIME.search(asked or ""):
        return text
    lines: list[str] = []
    for line, fence in zip(text.split("\n"), line_fences(text), strict=True):
        kept = line if fence is not None else _without_clock(line)
        if kept is not None:
            lines.append(kept)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return body or text
