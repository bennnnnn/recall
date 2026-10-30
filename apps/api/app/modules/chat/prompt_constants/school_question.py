"""A school exercise, said beside the message: the textbook's answer, at its level.

A Class 8 physical science book's exercises (2026-10-30) got answers a student could not
hand in: "That's a riddle dressed as a question", "Where did this question come from?",
a multiple-choice answer that changed its mind and blamed the textbook, an umbrella
question argued with expected-value tables, electroplating aluminium sent to molten
cryolite at 1000 °C, and offers of more at the end. The reply's level follows the
question's; the note nearest the message is the one a small model keeps to.

An exercise is read from its shape only: options a, b, c; an assessment code ("(AS1)");
an exercise's opening verb ("Explain…", "Give two examples…", "Define…"); its closing
order ("…? Explain."); or a textbook's phrases ("with suitable examples", "in our daily
life", "Do you agree with the statement…").
"""

from __future__ import annotations

import re

from app.services.choice_options import lists_choices

_CODE = re.compile(r"\(\s*AS\s*\d\s*\)|\[\s*\]")
# "Explain how a mortgage works" is anyone's question: only an exercise's own orders.
_OPENING = re.compile(
    r"^\s*(?:\d{1,2}[.)]\s*)?(?:explain\s+(?:about|with)|define|distinguish\s+between"
    r"|differentiate\s+between|classify\s+the"
    r"|give\s+(?:reasons?\s+for|an?\s+examples?\s+(?:of|for)"
    r"|(?:two|three|four|five|few|any\s+two|any\s+three)\s+(?:\w+\s+)?examples?\s+(?:of|for|each))"
    r"|write\s+(?:the\s+differences?|a\s+short\s+note))\b",
    re.IGNORECASE,
)
# A multiple-choice stem states the question before its options ("Rayon is prepared by
# a) …"); "I bought a) bread b) milk" and "Plan: a) gym" are the user's own lists.
_FIRST_OPTION = re.compile(r"(?:^|(?<=[\s\[(]))\(?[aA][).\]]\s")
_OWN = re.compile(r"\b(?:i|i'm|my|me|we|our|us)\b", re.IGNORECASE)
_CLOSING = re.compile(
    r"(?:^|[.?!]\s*)(?:explain(?:\s+why)?|justify|discuss|(?:give|specify)\s+reasons?)"
    r"\s*[.?!]?\s*$",
    re.IGNORECASE,
)
_TEXTBOOK = re.compile(
    r"\bwith\s+(?:suitable\s+|an?\s+|some\s+)?examples?\b|\bin\s+(?:our|your)\s+daily\s+life\b"
    r"|\bdo\s+you\s+(?:agree|support)\b.*\bstatement\s*[:\"“'‘]|\bin\s+the\s+experiment\b"
    r"|\b(?:text\s?book|syllabus|exam(?:ination)?)\s+(?:question|answer)",
    re.IGNORECASE | re.DOTALL,
)

SCHOOL_QUESTION_NOTE = (
    "This message is a school exercise. Answer it as the textbook expects, for the "
    "student who asked, at the level the question is written: open with the answer itself "
    "in plain words, using the textbook's terms, then a short reason or two to four "
    "everyday examples. Stay at that level: no university detail, history or regional "
    "trivia it did not ask for, and no side claim you are unsure of. Take the question as "
    "written: never call it a trick or a riddle, never dispute its wording or the "
    "textbook, and never ask where it came from. End when the answer is complete, with no "
    "offer of more."
)
_CHOICE_NOTE = (
    " It is multiple choice: name the one correct option, its letter and words, first, "
    "then one or two lines on why; never change the option partway or name two."
)


def _multiple_choice(text: str) -> bool:
    first = _FIRST_OPTION.search(text)
    if first is None or not lists_choices(text):
        return False
    stem = text[: first.start()]
    return len(stem.split()) >= 3 and _OWN.search(stem) is None


def is_school_exercise(query: str) -> bool:
    text = query.strip()
    return bool(
        _multiple_choice(text)
        or _CODE.search(text)
        or _OPENING.search(text)
        or _CLOSING.search(text)
        or _TEXTBOOK.search(text)
    )


def school_question_hint(query: str) -> str | None:
    """The note for a school exercise, or None."""
    if not is_school_exercise(query):
        return None
    return SCHOOL_QUESTION_NOTE + (_CHOICE_NOTE if _multiple_choice(query) else "")
