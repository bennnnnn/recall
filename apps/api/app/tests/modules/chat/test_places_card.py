"""A searched places reply keeps the model's own list; the pages never become one.

"What is the best restaurant near me?" showed a card of the search's pages ("RECOMMENDED:
📍 The best things to do…", "Price$$$", "Image 86: A plate of food…"), and "the best
restaurants in Addis Ababa" lost the venue lists under its headings to one (2026-11-08).
"""

from __future__ import annotations

import json
from uuid import uuid4

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.modules import web_search as web_search_service
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.finalize_text import add_search_sources
from app.modules.chat.quality import detect_quality_issues
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.services.md_fence_scan import iter_closed_fences
from app.tests.modules.chat.chat_test_support import turn_deps

_ARTICLES = [
    WebSearchHit(
        title="The best restaurants in San Francisco right now",
        url="https://www.timeout.com/san-francisco/restaurants/best-restaurants-in-san-francisco",
        snippet=(
            "RECOMMENDED: 📍 The best things to do in San Francisco 🚗 The best weekend "
            "getaways from San Francisco. Copra. Indian. Japantown. 725 Columbus Avenue"
        ),
    ),
    WebSearchHit(
        title="Eat & Drink",
        url="https://www.fishermanswharf.org/eat-drink",
        snippet="Image 86: A plate of food at Kin Khao. Price$$$ 1658 Market St",
    ),
]


def _state(reply: str) -> FinalizeState:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[{"role": "user", "content": "What is the best restaurant near me?"}],
        run_title=False,
        user_message_content="What is the best restaurant near me?",
        reserved_tokens=0,
        max_output_tokens=0,
        search_sources=list(_ARTICLES),
        local_places=True,
    )
    return FinalizeState(
        deps=turn_deps(web_search=web_search_service),
        settings=Settings(),
        ctx=ctx,
        raw=reply,
        text=reply,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )


def test_the_pages_never_become_a_places_card() -> None:
    reply = (
        "There's no single best restaurant in San Francisco, but here are two standouts.\n\n"
        "🏆 Copra — Indian, in Japantown.\n\n🥇 Zuni Café — the Market Street institution."
    )
    state = _state(reply)
    out = add_search_sources(state)
    assert "```places" not in out
    assert "🏆 Copra — Indian, in Japantown." in out
    for junk in ("RECOMMENDED", "Image 86", "Eat & Drink"):
        assert junk not in out.split("```sources")[0]
    # The sources fence closes the reply, as the quality check wants it.
    codes = {signal.code for signal in detect_quality_issues(state.ctx, out).signals}
    assert "raw_sources_in_body" not in codes


def test_the_venue_lists_under_the_headings_stay() -> None:
    reply = (
        "Here are the Addis Ababa spots with the best word of mouth.\n\n"
        "### 🥘 Ethiopian classics\n\n1. **Yod Abyssinia** — traditional food and dancing\n"
        "2. **Kategna** — kitfo and tibs\n\n"
        "### 🌍 International and fine dining\n\n1. **Antica** — wood-fired pizza\n"
        "2. **Sishu** — burgers in Bole"
    )
    out = add_search_sources(_state(reply))
    prose = out.split("```sources")[0]
    assert "1. **Yod Abyssinia**" in prose
    assert "2. **Sishu** — burgers in Bole" in prose
    assert "```places" not in out


def test_a_card_keeps_only_the_addresses_its_pages_give() -> None:
    card = [
        {
            "name": "Copra",
            "url": "https://www.google.com/maps/search/?api=1&query=Copra%2C+725+Columbus+Avenue",
            "note": "Indian, Japantown",
            "address": "725 Columbus Avenue, San Francisco, CA 94133",
        },
        {"name": "Zuni Café", "url": "https://zunicafe.com", "address": "1658 Market St"},
    ]
    reply = f"The top pick near you is Copra.\n\n```places\n{json.dumps(card)}\n```\n\nEnjoy!"
    pages = [
        WebSearchHit(
            title="Zuni Café",
            url="https://zunicafe.com",
            snippet="Zuni Café, 1658 Market St, San Francisco. Open since 1979.",
        ),
        WebSearchHit(
            title="The best restaurants in San Francisco right now",
            url="https://www.timeout.com/sf",
            snippet=(
                "Copra. Indian. Japantown. Srijith Gopinathan's South Indian cooking is the "
                "most talked-about in town, and the dining room is as warm as the food. Book "
                "weeks ahead for the tasting menu, or sit at the bar for curries and dosas. "
                "Liguria Bakery. Focaccia only, sold until it runs out. 725 Columbus Avenue."
            ),
        ),
    ]
    state = _state(reply)
    state.ctx.search_sources = pages
    out = add_search_sources(state)
    [(_start, _end, body)] = list(iter_closed_fences(out, "places"))
    copra, zuni = json.loads(body)
    assert "address" not in copra
    assert copra["note"] == "Indian, Japantown"
    # The Maps link searched the borrowed address; it now finds the name in its town.
    assert "Columbus" not in copra["url"]
    assert "Copra%2C%20San%20Francisco%2C%20CA%2094133" in copra["url"]
    assert zuni["address"] == "1658 Market St"
    # The card stays where the model wrote it.
    assert out.startswith("The top pick near you is Copra.\n\n```places\n")
    assert "\n```\n\nEnjoy!" in out
