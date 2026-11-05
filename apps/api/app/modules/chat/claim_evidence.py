"""Whether a page states a claim the claim check flagged: read in code, not by the checker.

A cheap checker calls claims "unsupported" that a page says outright: "at least 76 deaths"
under "At least 76 people confirmed died", and "beat defending champions Brazil" under a
page with those words (2026-11-05). Cutting such a sentence costs the user a sourced
answer, so only a figure or a legal standing no page states is cut. A figure is stated
when one page holds every number in it. A claim with no figure is stated when one
sentence of a page holds most of its words and says it the same way: "Acme is not
licensed" is not stated by "Acme is licensed" (review of #2301).
"""

from __future__ import annotations

import re

from app.gateways.web_search_gateway import SNIPPET_CHARS, WebSearchHit

_FIGURE = re.compile(r"\d+(?:[.,]\d+)*")
_GROUPED = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_A_YEAR = re.compile(r"(?:19|20)\d\d")
_CUT_KINDS = frozenset({"figure", "legal", "status"})
_CONTENT_WORD = re.compile(r"[^\W\d_]{4,}")
# A word by its first letters, so "beating" is the page's "beat" (review of #2301).
_STEM = 4
# A claim with no figure is a sentence's when this share of its words are in it.
_MIN_WORDS_IN_SENTENCE = 0.8
_NEGATION = re.compile(r"\b(?:not|no|never|without|neither|nor|cannot)\b|n't\b", re.IGNORECASE)
_PAGE_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def figures(text: str) -> set[str]:
    """The numbers ``text`` states, "1,600" as "1600"; a year alone dates, it states nothing."""
    found = set()
    for figure in _FIGURE.findall(text):
        figure = figure.rstrip(".,")
        if _GROUPED.fullmatch(figure):
            figure = figure.replace(",", "")
        if not _A_YEAR.fullmatch(figure):
            found.add(figure)
    return found


def costs_its_sentence(quote: str, kind: str, pages: list[WebSearchHit]) -> bool:
    """A figure or a legal standing no page states: what a reader would act on and what a
    page would have said. An attribution or a detail beside the answer is not worth the
    sentence that carries the answer."""
    if kind == "figure" and not figures(quote):
        return False  # "three million" written out: no figure the pages can be read for
    return kind in _CUT_KINDS and not stated_by_a_page(quote, pages)


def stated_by_a_page(quote: str, pages: list[WebSearchHit]) -> bool:
    """Whether one page states ``quote``: every figure in it, or for a claim with none, one
    sentence with most of its words and the same negation."""
    wanted = figures(quote)
    words = _stems(quote)
    negated = _NEGATION.search(quote) is not None
    for page in pages:
        text = f"{page.title}\n{page.snippet[:SNIPPET_CHARS]}"
        if wanted:
            if wanted <= figures(text):
                return True
            continue
        if words and any(
            len(words & _stems(sentence)) / len(words) >= _MIN_WORDS_IN_SENTENCE
            and (_NEGATION.search(sentence) is not None) == negated
            for sentence in _PAGE_SENTENCE.split(text)
        ):
            return True
    return False


def _stems(text: str) -> set[str]:
    return {word.casefold()[:_STEM] for word in _CONTENT_WORD.findall(text)}
