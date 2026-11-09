"""A places card's address is the one a page gives that place, not the next entry's."""

from __future__ import annotations

import json

import pytest

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.web_search.place_addresses import keep_given_addresses
from app.services.md_fence_scan import iter_closed_fences

_LIST_ARTICLE = WebSearchHit(
    title="The best restaurants in San Francisco right now",
    url="https://www.timeout.com/sf",
    snippet=(
        "1. Arquet. Wood-fired California cooking in the Ferry Building, 1 Ferry Building. "
        "2. Copra. Indian. Japantown. Srijith Gopinathan's South Indian cooking is the most "
        "talked-about in town, and the dining room is as warm as the food. Book weeks ahead. "
        "3. Lunette. Cambodian street food. 725 Columbus Avenue."
    ),
)


def _card(*places: dict[str, str]) -> str:
    return f"Here you go.\n\n```places\n{json.dumps(list(places))}\n```\n"


def _places(text: str) -> list[dict[str, str]]:
    [(_start, _end, body)] = list(iter_closed_fences(text, "places"))
    rows: list[dict[str, str]] = json.loads(body)
    return rows


@pytest.mark.parametrize(
    "name, address, kept",
    [
        # Written right after the name: the entry's own.
        ("Arquet", "1 Ferry Building, San Francisco, CA 94111", True),
        # Another entry's: too far past Copra, and Lunette is on the card between them.
        ("Copra", "725 Columbus Avenue, San Francisco, CA 94133", False),
        ("Lunette", "725 Columbus Ave, San Francisco", True),
        # No page names this address at all.
        ("Copra", "1700 Post St, San Francisco", False),
        # A district or a landmark has no street number to hold against the pages.
        ("Copra", "Japantown, San Francisco", True),
    ],
)
def test_an_address_stays_only_when_a_page_gives_it_that_place(
    name: str, address: str, kept: bool
) -> None:
    card = _card(
        {"name": name, "url": "https://example.com/" + name.lower(), "address": address},
        {"name": "Lunette" if name != "Lunette" else "Arquet", "url": "https://example.com/x"},
    )
    place = _places(keep_given_addresses(card, [_LIST_ARTICLE]))[0]
    assert ("address" in place) is kept


def test_an_address_between_the_name_and_this_one_is_the_name_s() -> None:
    page = WebSearchHit(
        title="Where to eat",
        url="https://example.com/list",
        snippet="Copra, 1700 Post St. Tosca Cafe, 242 Columbus Ave.",
    )
    card = _card(
        {"name": "Copra", "url": "https://example.com/c", "address": "242 Columbus Ave"},
    )
    assert "address" not in _places(keep_given_addresses(card, [page]))[0]


def test_the_place_s_own_page_gives_its_address_anywhere() -> None:
    page = WebSearchHit(
        title="Franciscan Crab Restaurant - Fisherman's Wharf",
        url="https://franciscancrabrestaurant.com",
        snippet="2801 Taylor St, San Francisco. Open daily. " + "Bay views. " * 40,
    )
    card = _card({"name": "Franciscan Crab Restaurant", "address": "2801 Taylor Street"})
    assert _places(keep_given_addresses(card, [page]))[0]["address"] == "2801 Taylor Street"


_COPRA_ON_YELP = WebSearchHit(
    title=(
        "COPRA - Updated November 2026 - 1200 Photos & 500 Reviews - 1700 Post St, "
        "San Francisco, California - Indian - Yelp"
    ),
    url="https://www.yelp.com/biz/copra-sf",
    snippet="Specialties: South Indian cooking from chef Srijith Gopinathan.",
)
_ESSENTIALS = WebSearchHit(
    title="The 38 Essential San Francisco Restaurants",
    url="https://sf.eater.com/maps/best",
    snippet=(
        "Copra. Srijith Gopinathan, who earned two Michelin stars at Campton Place, opened "
        "this Japantown restaurant to showcase the cooking of his native Kerala; the tasting "
        "menu is a tour of the coast, the dining room is warm and the cocktail list is one of "
        "the best in town for anyone who loves spice. 1700 Post St, San Francisco, CA 94115"
    ),
)


@pytest.mark.parametrize(
    "page, place",
    [
        # A directory writes the address in its title.
        (_COPRA_ON_YELP, {"name": "Copra", "address": "1700 Post St, San Francisco"}),
        # A long write-up, its address at the end: the next place on the card is the limit,
        # not a count of characters.
        (_ESSENTIALS, {"name": "Copra", "address": "1700 Post St, San Francisco"}),
        # Pages leave out the name's "The".
        (
            WebSearchHit(
                title="Best", url="https://x.test", snippet="Slanted Door, 1 Ferry Building #3."
            ),
            {"name": "The Slanted Door", "address": "1 Ferry Building, San Francisco"},
        ),
        # "2 blocks from Dolores St" says how far, not where.
        (
            WebSearchHit(
                title="Best",
                url="https://x.test",
                snippet="Tartine Bakery is 2 blocks from Dolores St; find it at 600 Guerrero St.",
            ),
            {"name": "Tartine Bakery", "address": "600 Guerrero St, San Francisco"},
        ),
        # A range of house numbers holds the one the card gives.
        (
            WebSearchHit(
                title="Best", url="https://x.test", snippet="Zuni Café, 1658-1660 Market St."
            ),
            {"name": "Zuni Café", "address": "1658 Market St, San Francisco"},
        ),
    ],
)
def test_a_correct_address_stays(page: WebSearchHit, place: dict[str, str]) -> None:
    """Review of the first rule (2026-11-09): each of these lost a right address."""
    card = _card(place)
    assert keep_given_addresses(card, [page]) == card


def test_a_venue_list_fenced_as_json_is_checked_too() -> None:
    # The phone draws a ```json venue array as a places list.
    card = (
        "Here.\n\n```json\n"
        + json.dumps(
            [
                {"name": "Copra", "address": "725 Columbus Avenue, SF", "rating": 5},
                {"name": "Lunette", "address": "725 Columbus Avenue, SF"},
            ]
        )
        + "\n```\n"
    )
    out = keep_given_addresses(card, [_LIST_ARTICLE])
    assert out.startswith("Here.\n\n```json\n")
    copra, lunette = json.loads(out.split("```json\n")[1].split("\n```")[0])
    assert "address" not in copra
    assert copra["rating"] == 5
    assert lunette["address"] == "725 Columbus Avenue, SF"
    # A ```json fence of anything else is left alone.
    other = '```json\n[{"title": "x", "address": "725 Columbus Avenue"}]\n```'
    assert keep_given_addresses(other, [_LIST_ARTICLE]) == other


def test_a_maps_link_built_on_a_dropped_address_finds_the_name_in_town() -> None:
    card = _card(
        {
            "name": "Copra",
            "url": "https://www.google.com/maps/search/?api=1&query=Copra%2C+725+Columbus+Avenue",
            "address": "725 Columbus Avenue, San Francisco, CA 94133",
        },
        {"name": "Lunette", "url": "https://lunette.example", "address": "9 Nowhere St, SF"},
    )
    copra, lunette = _places(keep_given_addresses(card, [_LIST_ARTICLE]))
    assert "address" not in copra
    assert copra["url"].endswith("query=Copra%2C%20San%20Francisco%2C%20CA%2094133")
    # A venue's own site is no search: it stays.
    assert "address" not in lunette
    assert lunette["url"] == "https://lunette.example"


@pytest.mark.parametrize(
    "text",
    [
        "No card in this reply.",
        _card({"name": "Arquet", "address": "1 Ferry Building"}),
        "```places\nnot json\n```",
    ],
)
def test_a_reply_with_nothing_to_drop_is_unchanged(text: str) -> None:
    assert keep_given_addresses(text, [_LIST_ARTICLE]) == text
    assert keep_given_addresses(text, []) == text
