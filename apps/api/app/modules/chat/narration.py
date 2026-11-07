"""A reply speaks to the person, never about them or about what it was given.

A model's planning sometimes reaches the user above the answer. 'The user says "ok and like
5 common beginner mistakes i should avoid?" This is a factual list request, so I'll give five
…' (2026-11-06). "Memory says they've been learning useful English words, one concept at a
time, and they're on a fresh subject now, so this is a new lesson. Since they asked for a
whole subject, I'll teach Lesson 1 …" opened a lesson (2026-11-07). Both talk about the
person in the third person, or about memory, to nobody, and say what the model will do.

An opening paragraph like that goes, and so does a second one right after it. A paragraph
that says "you" is speaking to the person and stays ("You've been learning English words,
so…"); one that names no plan stays ("The user wants to log in, so the app redirects to
/auth"). "Memory says you…" at a paragraph's start loses its first words: what is
remembered is said to the person, not credited to memory.
"""

from __future__ import annotations

import re

from app.services.text_normalize import straighten_apostrophes

# The person who asked, as the model's notes call them, or memory as the source.
_NAMES_THE_ASKER = re.compile(
    r"\bthe (?:user|learner|student)(?:'s message)? (?:says|said|asks|asked|wants|wanted"
    r"|writes|wrote|is asking|is requesting|requests|requested|needs|is looking for"
    r"|is learning|has been learning|is on|knows|already knows|prefers|mentioned)\b"
    # Memory as the source about them; never memory a program keeps ("kept in memory").
    r"|\b(?:my |their |saved )?memory (?:says|said|notes|mentions|indicates)\b"
    r"|\b(?:according to|based on) (?:the |their |my |saved )?memory\b",
    re.IGNORECASE,
)
# A bare "they" is the asker only in talk about this turn: "They want a lesson on proverbs,
# so I'll …"; "They asked me to stay, but I'll go." is a story.
_THEY_THE_ASKER = re.compile(
    r"\bthey(?:'ve| have)? (?:asked|been learning|already know|mentioned|requested)\b"
    r"|\bthey(?:'re| are) (?:asking|learning|on a|on lesson|new to|looking for)\b"
    r"|\bthey (?:want|wanted|prefer)\b",
    re.IGNORECASE,
)
_ABOUT_THIS_TURN = re.compile(
    r"\b(?:lessons?|subject|topic|question|request|message|memory|course|chat|conversation)\b",
    re.IGNORECASE,
)
_TO_THEM = re.compile(r"\byou(?:'ve|'re|'ll|'d)?\b|\byour\b", re.IGNORECASE)
# What the model will do: "I'll teach", "let me", "so this is a new lesson".
_ANNOUNCES_PLAN = re.compile(
    r"\b(?:i(?:'ll| will| should| need to| am going to|'m going to)|let me)\b"
    r"|\bso this is\b",
    re.IGNORECASE,
)
_PLAN_PARAGRAPH = 500
_MOST_PARAGRAPHS = 2
# "Memory says you're vegetarian, so …", "According to my memory, you …".
# Only before a clause about them: "The memory shows you the value of x" is a debugger's.
_MEMORY_LEAD = re.compile(
    r"(?:(?:my )?memory (?:says|notes|tells me)(?: that)?"
    r"|(?:according to|based on) (?:my )?memory,?)\s+"
    r"(?=you(?:'re|'ve|'d| are| have| were| live| like| prefer| want| work| study)\b)",
    re.IGNORECASE,
)


def narrates_the_turn(paragraph: str) -> bool:
    """``paragraph`` is short, talks about the person or memory without speaking to them,
    and says what the model will do. One that opens on a quotation is a story's."""
    prose = straighten_apostrophes(paragraph)
    if len(prose) > _PLAN_PARAGRAPH or prose.lstrip().startswith(('"', "\u201c")):
        return False
    about_them = _NAMES_THE_ASKER.search(prose) is not None or (
        _THEY_THE_ASKER.search(prose) is not None and _ABOUT_THIS_TURN.search(prose) is not None
    )
    return (
        about_them and _TO_THEM.search(prose) is None and _ANNOUNCES_PLAN.search(prose) is not None
    )


def without_narration(text: str) -> str:
    """``text`` without its opening paragraphs that narrate the turn, and with "Memory says"
    off a sentence that speaks to the person; as it was when nothing would be left."""
    rest = text.lstrip()
    for _ in range(_MOST_PARAGRAPHS):
        plan, gap, after = rest.partition("\n\n")
        if not (gap and after.strip() and narrates_the_turn(plan)):
            break
        rest = after.lstrip("\n")
    lead = _MEMORY_LEAD.match(straighten_apostrophes(rest))
    if lead is not None:
        rest = rest[lead.end() :]
        rest = rest[:1].upper() + rest[1:]
    return text if rest == text.lstrip() else rest
