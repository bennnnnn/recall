"""A multiple-choice question from a book: its answer is one of the options it lists.

"The lowest temperature at which a substance catches fire is called its a) Ignition
temperature b) Maximum temperature c) Room temperature d) Normal temperature" was answered
from a search that cited a YouTube comment and a homework site, with a note that "the
sources do not specify" a detail no one asked about (2026-10-30, a Class 8 book). A
choice between products, prices or anything current still searches.
"""

from __future__ import annotations

import re

from app.modules.web_search.live_asks import asks_for_job_listings
from app.modules.web_search.recency import asks_for_newest, wants_dated_results
from app.services.choice_options import lists_choices

# A choice to buy or a price: what is on sale changes.
_SHOPPING = re.compile(
    r"\b(?:buy|purchase|price|cost|cheap(?:er|est)?|deal|subscription|plan|which\s+(?:phone|laptop"
    r"|car|stock|crypto|coin|app|brand|model))\b",
    re.IGNORECASE,
)


def asks_textbook_choice(text: str) -> bool:
    """Options a, b, c (and d) in order, and nothing current to choose between."""
    return lists_choices(text) and not (
        _SHOPPING.search(text)
        or asks_for_newest(text)
        or wants_dated_results(text)
        or asks_for_job_listings(text)
    )
