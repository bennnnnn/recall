"""A searched reply's brackets that only credit its own sources go; the chips name them."""

from __future__ import annotations

import pytest

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.web_search import drop_source_credits

_HITS = [
    WebSearchHit("Handwashing | CDC", "https://www.cdc.gov/handwashing", ""),
    WebSearchHit("Employment Situation Summary", "https://www.bls.gov/news", ""),
    WebSearchHit("Credit Scores | Consumer Advice", "https://consumer.ftc.gov/articles/x", ""),
    WebSearchHit("Credit reports and scores | USAGov", "https://www.usa.gov/credit-reports", ""),
    WebSearchHit("What Affects Your Credit Scores? - Experian", "https://www.experian.com/b", ""),
    WebSearchHit(
        "How to improve your credit score - Broadview Federal Credit Union",
        "https://www.broadviewfcu.com/learn",
        "",
    ),
    WebSearchHit("5 ways to build credit | First Southwest Bank", "https://www.fswb.bank/a", ""),
]


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # 2026-11-06, "what is a credit score and how do i improve it" on the free model.
        (
            "Payment history is about **35% of your FICO score** (Experian).",
            "Payment history is about **35% of your FICO score**.",
        ),
        (
            "A higher score gets you lower rates (USAGov, FTC).",
            "A higher score gets you lower rates.",
        ),
        (
            "Keep balances low (First Southwest Bank). Pay on time (Broadview)",
            "Keep balances low. Pay on time",
        ),
        ("Errors drag your score down (Experian and USA.gov).", "Errors drag your score down."),
    ],
)
def test_a_bracket_crediting_this_turns_sources_goes(reply: str, kept: str) -> None:
    assert drop_source_credits(reply, _HITS) == kept


@pytest.mark.parametrize(
    "reply",
    [
        # An aside, a number, a source this turn never had, a link.
        "Keep card balances low (ideally under 30%).",
        "Pay on time (this matters most).",
        "Scores run 300-850 (FICO 8).",
        "Reuters reported a rate cut (Reuters).",
        # A word that is only somewhere in a result's title (review of #2321).
        "Pay it (It helps).",
        "Weigh it (Credit).",
        # A name that is the content, even when it is one of the results (review of #2321).
        "Fix mistakes with the bureaus (Experian, USAGov), since errors drag it down.",
        "Ask the bank (First Southwest Bank).",
        "The lender (Broadview) raised rates.",
        # A credit right after "the better" stays too: it reads like "the company (Tesla)".
        "The higher your score, the better (USAGov, FTC).",
        "See [Experian](https://www.experian.com/b) for your report.",
        # The short form of the name just before it, which the reply may use again.
        "Complain to the Federal Trade Commission (FTC) if a bureau ignores you.",
        "Ask the Centers for Disease Control and Prevention (CDC).",
        "Data from the Bureau of Labor Statistics (BLS).",
        '```json\n{"note": "from (Experian)"}\n```',
    ],
)
def test_any_other_bracket_stays(reply: str) -> None:
    assert drop_source_credits(reply, _HITS) == reply


def test_a_turn_without_sources_is_left_alone() -> None:
    assert drop_source_credits("A fact (Experian).", []) == "A fact (Experian)."
