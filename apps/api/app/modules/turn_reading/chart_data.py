"""Which chart a message asks to draw of the user's own numbers, and of what kind.

The server draws a bar, pie, line or histogram chart of numbers the user wrote
(``modules/charts``); these say which turns those are, from the user's words alone.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.modules.turn_reading.chart import (
    chart_followup_data,
    chart_of_public_facts,
    holds_data,
    is_chart_question,
)
from app.services.prompt_safety import text_before_attachment_markers


def own_data_chart(query: str, prior_messages: Sequence[tuple[str, str]] | None) -> str | None:
    """The message whose numbers a chart of the user's own data draws: this one when it asks
    for a chart and lists the numbers ("bar chart: rent 1200, food 400, transport 150"), an
    earlier one when it points back ("graph it", "now a pie chart"); None for any other turn
    (a curve y = f(x), a chart of facts a search finds, code that draws one, no numbers)."""
    cleaned = query.strip()
    if is_chart_question(cleaned) and holds_data(cleaned) and not chart_of_public_facts(cleaned):
        return " ".join(text_before_attachment_markers(cleaned).split())
    return chart_followup_data(cleaned, prior_messages) or None


# The kind of chart a message names. Bars, a pie, a line and a histogram are the server's to
# draw from the user's numbers; any other named kind (a scatter plot, a box plot, an area
# chart) is not, so the server draws none for it.
_NAMED_KINDS = (
    ("histogram", re.compile(r"\bhistograms?\b", re.IGNORECASE)),
    ("pie", re.compile(r"\b(?:pie|donut|doughnut)\s*(?:charts?|graphs?)?\b", re.IGNORECASE)),
    ("bar", re.compile(r"\b(?:bar|column)\s*(?:charts?|graphs?|plots?)\b", re.IGNORECASE)),
    # A "line plot" is a dot plot in many schools: not a line chart, so not the server's.
    ("line", re.compile(r"\bline\s*(?:charts?|graphs?)\b", re.IGNORECASE)),
    (
        "other",
        re.compile(
            r"\b(?:scatter\s*(?:plots?|charts?|graphs?)?|scatterplots?|line\s*plots?|box(?:[\s-]+and[\s-]+"
            r"whiskers?)?[\s-]*(?:plots?|charts?)|dot\s*plots?|area\s*(?:charts?|graphs?)|"
            r"stacked|grouped|radar|bubble|waterfall|heat\s*maps?|pictographs?|stem[\s-]+and"
            r"[\s-]+leaf)\b",
            re.IGNORECASE,
        ),
    ),
)


def named_chart_kind(text: str) -> str | None:
    """ "bar", "pie", "line" or "histogram" when the message names that kind of chart,
    "other" when it names another kind (or two kinds), None when it names none ("chart my
    steps", "graph it")."""
    named = {kind for kind, pattern in _NAMED_KINDS if pattern.search(text)}
    if not named:
        return None
    return named.pop() if len(named) == 1 else "other"
