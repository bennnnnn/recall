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

The plan may be said in the present tense, and in the answer's own paragraph: "The user asks
what Bahir Dar has, a follow-up to the size question, so I give new points, not a recap. The
user prefers brief replies, so I keep it short." opened a free-chat reply (2026-11-27). Such
a plan is one only when it is about the reply (its question, length or points): "The user
wants to sign in quickly, so I put the button first" is a design answer's and stays. The
narrating sentences that lead a paragraph go, and the answer after them stays. So does an
opening on the model's own earlier reply, in the prompt's words, said to the user ("Your
last reply gave six energy types, so "the second one" is wind.", Pro, 2026-11-27); "Your
last reply to Sam sounded cold" is about the user's own message and stays. "Memory says
you…" loses its first words at any paragraph's start.
"""

from __future__ import annotations

import re

from app.services.text_normalize import straighten_apostrophes

# The person who asked, as the model's notes call them, or memory as the source.
_NAMES_THE_ASKER = re.compile(
    r"\bthe (?:user|learner|student)(?:'s message)? (?:says|said|asks|asked|wants|wanted"
    r"|writes|wrote|is asking|is requesting|requests|requested|needs|is looking for"
    r"|is learning|has been learning|is on|knows|already knows|prefers|mentioned"
    r"|is a|is an|follows up|followed up|likes)\b"
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
# The same plan in the present tense ("so I give new points", "I keep it short"), counted
# only beside words about the reply itself (``_ABOUT_THE_REPLY``).
_PRESENT_PLAN = re.compile(
    r"\bso i(?:'m)? [a-z]+|\bi (?:keep|give|focus|stick|list|cover|answer|explain|add|skip"
    r"|offer|start|lead|go|aim|stay|use|include|write|make|provide|share|mention|avoid)\b"
    r"|\bso here(?:'s| is| are)\b",
    re.IGNORECASE,
)
_ABOUT_THE_REPLY = re.compile(
    r"\b(?:repl(?:y|ies)|answers?|responses?|recap|follow-?ups?|questions?|messages?"
    r"|requests?)\b|\bkeep (?:it|this) (?:short|brief)\b",
    re.IGNORECASE,
)
# The prompt's name for the model's own last reply, as the user's: never "… to Sam".
_EARLIER_REPLY = re.compile(
    r"(?:in )?your (?:last|previous|earlier) (?:reply|answer|response)\b(?! to\b)", re.IGNORECASE
)
_SENTENCE = re.compile(r"[^.!?\n]*[.!?]+(?=\s|$)")
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
    if not about_them or _TO_THEM.search(prose) is not None:
        return False
    if _ANNOUNCES_PLAN.search(prose) is not None:
        return True
    return _PRESENT_PLAN.search(prose) is not None and _ABOUT_THE_REPLY.search(prose) is not None


def _narrating_lead(paragraph: str) -> int:
    """Where the sentences at the start of ``paragraph`` that narrate the turn end (0 when
    it opens on anything else)."""
    at = 0
    while (sentence := _SENTENCE.match(paragraph, at)) is not None:
        said = sentence.group(0).strip()
        if not (narrates_the_turn(said) or _EARLIER_REPLY.match(straighten_apostrophes(said))):
            break
        at = sentence.end()
    return at


def _narrates(paragraph: str) -> bool:
    """The whole paragraph narrates the turn: as one, or sentence by sentence."""
    return narrates_the_turn(paragraph) or not paragraph[_narrating_lead(paragraph) :].strip()


def _without_narrating_lead(paragraph: str) -> str:
    """``paragraph`` without the sentences at its start that narrate the turn, when the
    answer follows them in it; as it was otherwise."""
    at = _narrating_lead(paragraph)
    rest = paragraph[at:].lstrip()
    return rest if at and rest else paragraph


def without_narration(text: str) -> str:
    """``text`` without its opening paragraphs that narrate the turn, and with "Memory says"
    off a sentence that speaks to the person; as it was when nothing would be left."""
    rest = text.lstrip()
    for _ in range(_MOST_PARAGRAPHS):
        plan, gap, after = rest.partition("\n\n")
        if not (gap and after.strip() and plan.strip() and _narrates(plan)):
            break
        rest = after.lstrip("\n")
    rest = "\n\n".join(
        _without_memory_lead(part) for part in _without_narrating_lead(rest).split("\n\n")
    )
    return text if rest == text.lstrip() else rest


def _without_memory_lead(paragraph: str) -> str:
    """``paragraph`` without "Memory says" before a clause about the person."""
    lead = _MEMORY_LEAD.match(straighten_apostrophes(paragraph))
    if lead is None:
        return paragraph
    rest = paragraph[lead.end() :]
    return rest[:1].upper() + rest[1:]
