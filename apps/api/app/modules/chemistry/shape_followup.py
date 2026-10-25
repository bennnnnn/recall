"""A line that only asks to see the molecules of the shape question before it.

Live failure (2026-10-25): after "Why is water bent tho, co2 isnt" the student wrote "Can u show
me both", which a photo search for "both" took, then "lol no the molecules", which got ASCII
art in a code box and a broken CO2 drawing. The server draws each molecule of a verified shape
answer (``chem_scene``), so a line that only asks to see them gets that answer again.

The whole line must be one of these, with fillers ("lol", "no", "pls", "can u"): a verb that
shows ("show me", "draw", "let me see") with a pronoun, a count or a noun ("both", "them",
"the molecules", "the shapes"); "what do they look like"; or the noun alone ("lol no the
molecules"). The shape question is the latest earlier user line that is not such a line
itself, so "the molecules" after "show me both" still finds it; any other line in between
declines. "show me both" after a crocodile and an alligator is not a shape question, and
stays a photo.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from typing import Any

from app.modules.chemistry.extractors.shapes import shape_question
from app.services.problem_followup import followup_line, message_role_content

_LEAD = (
    r"(?:(?:ok(?:ay)?|lol|lmao|haha|no|nah|nope|i\s+mean|so|and|but|yes|yeah|yep|pls|please|"
    r"just|now|then)[\s,.!]+)*"
)
_ASK = r"(?:(?:can|could|will|would)\s+(?:u|you)\s+(?:pls\s+|please\s+)?)?"
_VERB = (
    r"(?:(?:show|draw|display|sketch)(?:\s+(?:me|us))?|let\s+me\s+see|"
    r"i\s+(?:want|wanna|need)\s+(?:to\s+)?see|see)"
)
_NOUN = r"(?:molecules?|shapes?|structures?|drawings?|pictures?|diagrams?|models?)"
_COUNT = r"(?:both|them|those|these|each|all|it)"
_OBJECT = (
    rf"(?:{_COUNT}(?:\s+(?:of\s+)?(?:them\s+|the\s+)?{_NOUN})?"
    rf"|(?:the\s+|both\s+|those\s+|these\s+|each\s+)?{_NOUN}(?:\s+of\s+(?:them|both|those|each))?)"
)
_TAIL = r"(?:[\s,]+(?:pls|please|lol|too|then|again|now|instead|thanks|thx))*"
SHOW_LINE = re.compile(
    rf"{_LEAD}(?:{_ASK}{_VERB}(?:\s+{_OBJECT})?"
    r"|what\s+(?:do|does)\s+(?:they|it|those|these|both)\s+look\s+like"
    r"|how\s+do\s+(?:they|those)\s+look"
    rf"|(?:the\s+|both\s+|those\s+)?{_NOUN}){_TAIL}",
    re.IGNORECASE,
)
# Earlier user lines read for the shape question; show lines between are passed.
_MAX_LINES = 4


def is_show_line(text: str | None) -> bool:
    line = followup_line(text)
    return line is not None and SHOW_LINE.fullmatch(line) is not None


def _user_lines(recent: Sequence[Any]) -> Iterator[str]:
    seen = 0
    for message in reversed(recent):
        role, content = message_role_content(message)
        if role != "user" or not content or not content.strip():
            continue
        yield content
        seen += 1
        if seen == _MAX_LINES:
            return


def shape_followup_problem(line: str, recent: Sequence[Any]) -> str | None:
    """The shape question whose molecules this line asks to see, or None."""
    if not is_show_line(line):
        return None
    for earlier in _user_lines(recent):
        if is_show_line(earlier):
            continue
        return earlier if shape_question(earlier) is not None else None
    return None
