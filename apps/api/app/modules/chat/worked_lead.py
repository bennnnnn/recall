"""A worked solution states its result once, after the working, never as a guess above it.

Told to answer first, a model opened worked replies with a number it had not worked yet:
"The ratio of fuel used … is **5 : 7**" over working and a card that found 4 : 5, and
"The car covers **290 m**" over a sum of 310 m (a Class 9 book, 2026-10-30); the prompt
saying a calculation opens with its working did not hold. In a reply with a Given section
and an answer card, a short lead above Given that states a number is that guess, and goes.
A heading, a photo or a lead without a number stays, and so does a long lead, which may be
an answer of its own.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import iter_fences, line_fences

_GIVEN = re.compile(r"^[^\S\n]*(?:#{1,4}[^\S\n]+)?\*\*Given:?\*\*:?[^\S\n]*$", re.I | re.M)
_HEADING = re.compile(r"^\s*(?:#{1,6}\s|\*\*[^*]+\*\*\s*$)")
_KEEP = re.compile(r"^\s*\[Image:", re.I)
_DIGIT = re.compile(r"\d")
_MOST_WORDS = 60


def _paragraphs(lead: str) -> list[str]:
    return [part for part in re.split(r"\n[^\S\n]*\n", lead) if part.strip()]


def _a_guess(paragraph: str) -> bool:
    """Prose that states a number: not a heading, a photo or a fence."""
    stripped = paragraph.strip()
    if _HEADING.match(stripped) or _KEEP.match(stripped) or stripped.startswith("```"):
        return False
    return _DIGIT.search(stripped) is not None


def drop_guessed_lead(text: str) -> str:
    """``text`` without a short numeric lead above its Given section, when it has a card."""
    given = _GIVEN.search(text)
    if given is None:
        return text
    if not any(
        fence.lang == "answer" and fence.start > given.start() for fence in iter_fences(text)
    ):
        return text
    # A Given inside a fence (an example in code) is not the reply's.
    if line_fences(text)[text.count("\n", 0, given.start())] is not None:
        return text
    lead = text[: given.start()]
    if len(lead.split()) > _MOST_WORDS or not lead.strip():
        return text
    kept = [paragraph for paragraph in _paragraphs(lead) if not _a_guess(paragraph)]
    if len(kept) == len(_paragraphs(lead)):
        return text
    head = "\n\n".join(paragraph.strip("\n") for paragraph in kept)
    return f"{head}\n\n{text[given.start() :]}" if head else text[given.start() :]
