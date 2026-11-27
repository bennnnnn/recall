"""A reply speaks to the person, never about them or about what it was given.

A model's planning sometimes reaches the user above the answer. 'The user says "ok and like
5 common beginner mistakes i should avoid?" This is a factual list request, so I'll give five
…' (2026-11-06). "Memory says they've been learning useful English words, one concept at a
time, and they're on a fresh subject now, so this is a new lesson. Since they asked for a
whole subject, I'll teach Lesson 1 …" opened a lesson (2026-11-07). Both talk about the
person in the third person, or about memory, to nobody, and say what the model will do.

An opening paragraph like that goes, and so does a second one right after it. A paragraph
that says "you" is speaking to the person and stays whole ("You've been learning English
words, so…"; the prompt's "your last reply" below is not speaking to them); one that names no
plan stays ("The user wants to log in, so the app redirects to /auth"). "Memory says you…" at
a paragraph's start loses its first words: what is remembered is said to the person, not
credited to memory.

The plan may be said in the present tense, and in the answer's own paragraph: "The user asks
what Bahir Dar has, a follow-up to the size question, so I give new points, not a recap. The
user prefers brief replies, so I keep it short." opened a free-chat reply (2026-11-27). Such
a plan is one only when it is about the reply's shape (its length, a recap, a follow-up, its
replies): "The user wants to sign in quickly, so I put the button first" is a design answer's
and stays, and so is any present-tense plan when the user's message is about a bot, an app or
its users ("The user asks a question outside the docs, so I answer with a fallback
message."). The narrating sentences that lead a paragraph go, and the answer after them stays.
So does an opening on the model's own earlier reply, in the prompt's words, that works out
what the message points to or what comes next ("Your last reply gave six energy types, so
"the second one" is wind.", Pro, 2026-11-27). The user's own reply or answer is theirs:
"Your last reply to Sam sounded cold" and tutoring feedback ("Your previous answer, 12, was
off by two") stay. "Memory says you…" loses its first words at any paragraph's start outside
a code fence.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import line_fences
from app.services.text_normalize import straighten_apostrophes

# The person who asked, as the model's notes call them, or memory as the source.
_NAMES_THE_ASKER = re.compile(
    r"\bthe (?:user|learner|student)(?:'s message)? (?:says|said|asks|asked|wants|wanted"
    r"|writes|wrote|is asking|is requesting|requests|requested|needs|is looking for"
    r"|is learning|has been learning|is on|knows|already knows|prefers|mentioned"
    r"|is a|is an|follows up|followed up|likes|means|meant|is referring to|refers to"
    r"|typed|misspelled|misspelt)\b"
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
# The reply's own shape, which only a plan about this turn speaks of: "so I keep it short", "a
# follow-up …, so I give new points, not a recap". A bot's design speaks of questions, answers
# and messages too, so those words count for nothing here (review of #2609).
_ABOUT_THE_REPLY = re.compile(
    r"\b(?:repl(?:y|ies)|recap|follow-?ups?|new points)\b"
    r"|\bkeep (?:it|this|the answer|the reply) (?:short|brief|simple)\b",
    re.IGNORECASE,
)
# The user's message is about a bot, an app or its users: a first-person plan there is the
# design the answer describes.
_ABOUT_A_PRODUCT = re.compile(
    r"\b(?:chat ?bots?|bots?|assistants?|agents?|apps?|products?|users?|customers?|personas?"
    r"|ux|ui|support|tickets?|user stor(?:y|ies)|onboarding|flows?)\b",
    re.IGNORECASE,
)
# The prompt's name for the model's own last reply, said to the user, when the sentence goes
# on to work out what the message points to or what comes next ("…, so "the second one" is
# wind", "…, but the item you're asking about is…"). Never the user's own reply or answer:
# "Your last reply to Sam", "Your previous answer, 12, was off by two" (review of #2609).
_EARLIER_REPLY = re.compile(
    r"(?:in )?your (?:last|previous|earlier) repl(?:y|ies)\b(?! to\b)[^.!?\n]{0,40}?"
    r"\b(?:gave|offered|covered|listed|named|showed|included|mentioned|ended|suggested)\b"
    r"[^.!?\n]*?,\s*(?:so|but)\b",
    re.IGNORECASE,
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


def narrates_the_turn(paragraph: str, *, product: bool = False) -> bool:
    """``paragraph`` is short, talks about the person or memory without speaking to them,
    and says what the model will do. One that opens on a quotation is a story's. ``product``:
    the user's message is about a bot, an app or its users, so a present-tense plan is the
    design the answer describes."""
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
    return (
        not product
        and _PRESENT_PLAN.search(prose) is not None
        and _ABOUT_THE_REPLY.search(prose) is not None
    )


def _speaks_to_them(paragraph: str) -> bool:
    """The paragraph says "you" to the person, the prompt's "your last reply" aside."""
    prose = _EARLIER_REPLY.sub(" ", straighten_apostrophes(paragraph))
    return _TO_THEM.search(prose) is not None


def _narrating_lead(paragraph: str, *, product: bool) -> int:
    """Where the sentences at the start of ``paragraph`` that narrate the turn end (0 when
    it opens on anything else, or when the paragraph speaks to the person)."""
    if _speaks_to_them(paragraph):
        return 0
    at = 0
    while (sentence := _SENTENCE.match(paragraph, at)) is not None:
        said = sentence.group(0).strip()
        if not (
            narrates_the_turn(said, product=product)
            or _EARLIER_REPLY.match(straighten_apostrophes(said))
        ):
            break
        at = sentence.end()
    return at


def _narrates(paragraph: str, *, product: bool) -> bool:
    """The whole paragraph narrates the turn: as one, or sentence by sentence."""
    if narrates_the_turn(paragraph, product=product):
        return True
    at = _narrating_lead(paragraph, product=product)
    return bool(at) and not paragraph[at:].strip()


def _without_narrating_lead(paragraph: str, *, product: bool) -> str:
    """``paragraph`` without the sentences at its start that narrate the turn, when the
    answer follows them in it; as it was otherwise."""
    at = _narrating_lead(paragraph, product=product)
    rest = paragraph[at:].lstrip()
    return rest if at and rest else paragraph


def without_narration(text: str, asked: str = "") -> str:
    """``text`` without its opening paragraphs that narrate the turn, and with "Memory says"
    off a sentence that speaks to the person; as it was when nothing would be left.
    ``asked`` is the user's message."""
    product = _ABOUT_A_PRODUCT.search(asked) is not None
    rest = text.lstrip()
    for _ in range(_MOST_PARAGRAPHS):
        plan, gap, after = rest.partition("\n\n")
        if not (gap and after.strip() and plan.strip() and _narrates(plan, product=product)):
            break
        rest = after.lstrip("\n")
    if not rest.startswith(("```", "~~~")):
        first, gap, after = rest.partition("\n\n")
        rest = _without_narrating_lead(first, product=product) + gap + after
    rest = _without_memory_leads(rest)
    return text if rest == text.lstrip() else rest


def _without_memory_leads(text: str) -> str:
    """``text`` without "Memory says" before a clause about the person, at the start of each
    paragraph outside a code fence."""
    lines = text.split("\n")
    owners = line_fences(text)
    for index, line in enumerate(lines):
        if owners[index] is not None or (index and lines[index - 1].strip()):
            continue
        lead = _MEMORY_LEAD.match(straighten_apostrophes(line))
        if lead is not None:
            rest = line[lead.end() :]
            lines[index] = rest[:1].upper() + rest[1:]
    return "\n".join(lines)
