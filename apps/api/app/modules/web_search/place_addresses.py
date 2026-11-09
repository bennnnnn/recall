"""A places card's addresses, kept to the ones the reply's pages give each place.

A list article names many places and many addresses. The card put Copra, "Indian,
Japantown", at 725 Columbus Avenue in North Beach, an address the same article gave
another restaurant (2026-11-08). A page gives a place its address when it writes the
address soon after the place's name, with no other street address and no other place
on the card between them, or anywhere on the place's own page (its name in the title).
Any other address leaves the card, and its Maps link then finds the place by name in
its town.
"""

from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import quote

from app.gateways.web_search_gateway import WebSearchHit
from app.services.md_fence_scan import iter_closed_fences
from app.services.places_fence import PlaceFenceItem, parse_places_payload, places_payload_dicts

# How far past a place's name a page may write its address, in folded characters. A
# directory writes it beside the name; further on in a list article, the address is as
# likely the next entry's.
_AFTER_NAME = 200
# A name's first word this long stands for it ("Franciscan" for "Franciscan Crab Restaurant").
_NAME_WORD_MIN = 5
_HOUSE_AND_STREET = re.compile(r"^(\d+[a-z]?) ([a-z]+)")
# Any street address in folded text: a house number, up to four words, a street word.
_STREET_ADDRESS = re.compile(
    r"\b\d+[a-z]? (?:[a-z0-9]+ ){1,4}?"
    r"(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|way|pl|place|ct|court"
    r"|sq|square|pkwy|parkway|hwy|highway|plaza|building|bldg)\b"
)
# A Maps link searches the address it was written with; a venue's own site does not.
_MAPS_LINK = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*(?:google\.[a-z.]+/maps|maps\.google\.[a-z.]+/"
    r"|goo\.gl/maps|maps\.app\.goo\.gl/)",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    """Lower case, accents dropped, every run of other characters one space."""
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in plain if not unicodedata.combining(char)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


def _mention(form: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(form)}\b")


def _name_forms(name: str) -> list[re.Pattern[str]]:
    folded = _fold(name)
    words = folded.split()
    forms = [_mention(folded)] if folded else []
    if len(words) > 1 and len(words[0]) >= _NAME_WORD_MIN:
        forms.append(_mention(words[0]))
    return forms


def _last_name_end(before: str, forms: list[re.Pattern[str]]) -> int:
    """Where the last mention of the place ends in ``before``, else -1."""
    return max((found.end() for form in forms for found in form.finditer(before)), default=-1)


def _given_with(
    item: PlaceFenceItem, others: list[re.Pattern[str]], pages: list[WebSearchHit]
) -> bool:
    street = _HOUSE_AND_STREET.match(_fold(item.address))
    if street is None:
        # A district or a landmark: no street address to hold against the pages.
        return True
    address = _mention(f"{street.group(1)} {street.group(2)}")
    forms = _name_forms(item.name)
    for page in pages:
        text = _fold(page.snippet)
        title = _fold(page.title)
        if any(form.search(title) for form in forms) and address.search(text):
            return True
        for found in address.finditer(text):
            before = text[max(0, found.start() - _AFTER_NAME) : found.start()]
            end = _last_name_end(before, forms)
            if end < 0:
                continue
            between = before[end:]
            if _STREET_ADDRESS.search(between) or any(other.search(between) for other in others):
                continue
            return True
    return False


def _without_address(item: PlaceFenceItem) -> PlaceFenceItem:
    """The place with its address gone; a Maps link searching it now finds the name in town."""
    town = item.address.split(",", 1)[1].strip() if "," in item.address else ""
    url = item.url.strip()
    if not url or _MAPS_LINK.match(url):
        query = f"{item.name.strip()}, {town}" if town else item.name.strip()
        url = f"https://www.google.com/maps/search/?api=1&query={quote(query)}"
    return item.model_copy(update={"address": "", "url": url})


def _checked_fence(body: str, pages: list[WebSearchHit]) -> str | None:
    """The fence with each address the pages do not give left out; None when all stand."""
    try:
        items = parse_places_payload(json.loads(body.strip() or "[]"))
    except json.JSONDecodeError:
        return None
    names = [_fold(item.name) for item in items]
    kept = []
    for item, name in zip(items, names, strict=True):
        others = [_mention(other) for other in names if other and other != name]
        given = not item.address.strip() or _given_with(item, others, pages)
        kept.append(item if given else _without_address(item))
    if kept == items:
        return None
    payload = json.dumps(places_payload_dicts(kept), ensure_ascii=False)
    return f"```places\n{payload}\n```"


def keep_given_addresses(text: str, pages: list[WebSearchHit]) -> str:
    """Each ```places address the reply's pages give that place; the others left out."""
    if not pages or "```places" not in text.lower():
        return text
    pieces: list[str] = []
    cursor = 0
    for start, end, body in iter_closed_fences(text, "places"):
        checked = _checked_fence(body, pages)
        if checked is not None:
            pieces.append(text[cursor:start])
            pieces.append(checked + ("\n" if text[start:end].endswith("\n") else ""))
            cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)
