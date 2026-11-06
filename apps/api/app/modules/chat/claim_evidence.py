"""Whether a flagged claim costs its sentence: read in code, not by the checker.

A cheap checker calls claims "unsupported" that a page says outright: "at least 76 deaths"
under "At least 76 people confirmed died" (2026-11-05). Cutting such a sentence costs the
user a sourced answer. A figure is cut only when no page holds any number in it, and
a legal standing (licensed, banned, reinstated) is always cut: matching its words against
a page cleared contradicted ones ("Acme is licensed in Spain" under "Beta is licensed in
Spain, but Acme is licensed in France", review of #2301). An attribution or another detail
is never cut: "France ... beat defending champions Brazil" lost its sentence as a
"status" (2026-11-05), and the checker now names only a legal standing.
"""

from __future__ import annotations

import re

from app.gateways.web_search_gateway import SNIPPET_CHARS, WebSearchHit

_FIGURE = re.compile(r"\d+(?:[.,]\d+)*")
_GROUPED = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_A_YEAR = re.compile(r"(?:19|20)\d\d")
# Only "legal" is offered. A checker that still says "status" called December "dry season"
# one (2026-11-06): a detail, not a standing, so it costs nothing.
_LEGAL = frozenset({"legal"})


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
    """A legal standing, or a figure no page states: what a reader would act on. An
    attribution or a detail beside the answer is not worth the sentence that carries it."""
    if kind in _LEGAL:
        return True
    stated = figures(quote)
    # A figure written out ("three million") has no number the pages can be read for. One
    # that a page partly states is sourced: "28°C … until 10 AM" lost the temperature over
    # an hour no page gave, and the weather reply opened "That's the closest thing I have"
    # (2026-11-06). Only a figure no page holds any number of was made up.
    return kind == "figure" and bool(stated) and not any_on_a_page(stated, pages)


def any_on_a_page(wanted: set[str], pages: list[WebSearchHit]) -> bool:
    """Whether some page holds one of the figures in ``wanted``."""
    return any(wanted & figures(f"{page.title}\n{page.snippet[:SNIPPET_CHARS]}") for page in pages)
