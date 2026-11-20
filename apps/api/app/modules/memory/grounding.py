"""Hold every learned fact to the user's own words in the message it came from.

The memory model quotes the words that state each fact and says how the user said them
(``MemoryFactOp.quote`` / ``stated_as``). Its reading is the model's; these checks are the
server's, no IO:

- the quote is in one of the user lines the pass read, so a fact the model made up has
  no line to stand on, and that line's message becomes the fact's source;
- the fact shares a word with the quote where the two can be compared, so "Lawer" (a
  typo of "lawyer?") never becomes "User is a lawyer";
- only what the user stated about their own life is kept, unless they asked to remember it.

The owner's memory held "User is a lawyer", a 97-year-old wife, a job at Uber and a salary
from one provocative story, and "User is male (7M)" (2026-11-20).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.services.text_normalize import straighten_apostrophes

# How a fact was said (``schemas.MemoryFactOp.stated_as``): only this one is kept.
OWN_LIFE = "own_life"

_WORD = re.compile(r"\w+", re.UNICODE)
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")
# A parenthetical is the model's note on the claim ("User is male (7M)"), not the claim.
_PARENTHETICAL = re.compile(r"\([^)]*\)")
# Words that carry no claim: a fact sharing only these with its quote is not held by it.
# English only, as the fact sentences are written in English.
_FILLER = frozenset(
    """
    a an the and or but of to in on at for from with by as is are was were be been being
    am i me my mine we our us you your he she they them their his her its it this that
    these those has have had do does did not no so very just also now then there here
    user user's users who which what when where why how will would can could should
    about into over than too more most some any all each one own
    """.split()
)
# Two words are one when they share this long a start ("engineer", "engineering").
_STEM = 5


@dataclass(frozen=True)
class SourceLine:
    """One user line a pass read, and the message it came from (None for the fallback)."""

    text: str
    message_id: UUID | None = None


def _fold(text: str) -> str:
    folded = unicodedata.normalize("NFKC", straighten_apostrophes(text)).casefold()
    return " ".join(folded.split())


def _words(text: str) -> list[str]:
    return _WORD.findall(_fold(text))


def quoted_line(quote: str | None, lines: Sequence[SourceLine]) -> SourceLine | None:
    """The line the quote is copied from; parts joined by "..." must all be in it."""
    parts = [_fold(part).strip(" \"'.,!?;:") for part in _ELLIPSIS.split(quote or "")]
    parts = [part for part in parts if part]
    if not parts:
        return None
    for line in lines:
        body = _fold(line.text)
        if all(part in body for part in parts):
            return line
    return None


def _latin(word: str) -> bool:
    return all(char.isascii() for char in word)


def _comparable(quote_words: list[str], *, english: bool) -> bool:
    """Whether the quote is in the fact's language (English), so their words compare.

    Never for another script (Ge'ez, Cyrillic): the model's translation stands. In Latin
    script, always for a user whose app is in English; for anyone else only a one-word
    quote (a fragment, a typo) or one with an English filler word, so "Soy profesora en
    Madrid" keeps its translation.
    """
    if not quote_words or not all(_latin(word) for word in quote_words):
        return False
    return english or len(quote_words) == 1 or any(word in _FILLER for word in quote_words)


def _same_word(left: str, right: str) -> bool:
    if left == right:
        return True
    return len(left) >= _STEM and len(right) >= _STEM and left[:_STEM] == right[:_STEM]


def quote_holds_fact(quote: str, fact: str, *, english: bool = True) -> bool:
    """False when a comparable quote shares no claim word with the fact."""
    quote_words = _words(quote)
    if not _comparable(quote_words, english=english):
        return True
    claim = [
        word
        for word in _words(_PARENTHETICAL.sub(" ", fact))
        if word not in _FILLER and (len(word) > 1 or word.isdigit())
    ]
    if not claim:
        return True
    return any(_same_word(word, said) for word in claim for said in quote_words)


@dataclass(frozen=True)
class Grounding:
    """The line a fact stands on, or why it stands on none."""

    line: SourceLine | None
    reason: str


def ground_fact(
    *,
    quote: str | None,
    fact: str,
    stated_as: str | None,
    lines: Sequence[SourceLine],
    explicit_remember: bool,
    english: bool = True,
) -> Grounding:
    """Whether ``fact`` is the user's own word about their life, and on which line."""
    if stated_as != OWN_LIFE and not explicit_remember:
        return Grounding(None, f"said as {stated_as or 'nothing the model named'}")
    line = quoted_line(quote, lines)
    if line is None:
        return Grounding(None, "its quote is in none of the user's lines")
    if not quote_holds_fact(quote or "", fact, english=english):
        return Grounding(None, "its quote does not say it")
    return Grounding(line, "stated")


def grounded_source(
    *,
    quote: str | None,
    fact: str,
    stated_as: str | None,
    lines: Sequence[SourceLine],
    explicit_remember: bool,
    english: bool = True,
) -> SourceLine | None:
    """The user line that states ``fact`` about the user, or None to drop the fact."""
    return ground_fact(
        quote=quote,
        fact=fact,
        stated_as=stated_as,
        lines=lines,
        explicit_remember=explicit_remember,
        english=english,
    ).line


def line_saying(text: str, lines: Sequence[SourceLine]) -> SourceLine | None:
    """The line that holds ``text`` word for word (a fact the server read itself)."""
    return quoted_line(text, lines)
