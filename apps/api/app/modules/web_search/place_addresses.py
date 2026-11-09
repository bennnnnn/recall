"""A places list's addresses, kept to the ones the reply's pages give each place.

A list article names many places and many addresses. The card put Copra, "Indian,
Japantown", at 725 Columbus Avenue in North Beach, an address the same article gave
another restaurant (2026-11-08). A page gives a place its address when it writes the
address after the place's name with no other street address and no other place on the
card between them, or anywhere on the place's own page (its name in the title, where a
directory such as Yelp also writes the address). Any other address leaves the list, and
its Maps link then finds the place by name in its town. A venue list the model fenced as
```json is a places list too: the phone draws it as one.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import quote

from app.gateways.web_search_gateway import WebSearchHit
from app.services.md_fence_scan import iter_fences

_LIST_LANGS = frozenset({"places", "json"})
# A name's first word this long stands for it ("Franciscan" for "Franciscan Crab Restaurant").
_NAME_WORD_MIN = 5
# A house number (or a range of them, "1658-1660") and the street's first word.
_HOUSE_AND_STREET = re.compile(r"^(\d+[a-z]?)(?: \d+[a-z]?)? ([a-z]+)")
# Any street address in folded text: a house number, a few words naming the street, and a
# street word. "2 blocks from Dolores St" is a distance to a street, not an address.
_STREET_ADDRESS = re.compile(
    r"\b\d+[a-z]?(?: \d+[a-z]?)? "
    r"(?:(?!(?:from|to|of|off|near|at|past|away|blocks?|miles?|minutes?|mins?|km|meters?"
    r"|metres?|feet|ft|steps?|walk)\b)[a-z0-9]+ ){1,4}?"
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
    """Lower case, accents dropped, a sentence's end kept as " . " and every other run of
    characters one space: "3. Lunette. Cambodian street food." is no "3 … Street"."""
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in plain if not unicodedata.combining(char)).lower()
    return " ".join(re.sub(r"[^a-z0-9.!?;]+", " ", re.sub(r"[.!?;]+", " . ", plain)).split())


def _place_name(name: str) -> str:
    """The name as pages write it: "The Slanted Door" is often "Slanted Door"."""
    return _fold(name).removeprefix("the ")


def _mention(form: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(form)}\b")


def _name_forms(name: str) -> list[re.Pattern[str]]:
    folded = _place_name(name)
    words = folded.split()
    forms = [_mention(folded)] if folded else []
    if len(words) > 1 and len(words[0]) >= _NAME_WORD_MIN:
        forms.append(_mention(words[0]))
    return forms


def _last_name_end(before: str, forms: list[re.Pattern[str]]) -> int:
    """Where the last mention of the place ends in ``before``, else -1."""
    return max((found.end() for form in forms for found in form.finditer(before)), default=-1)


def _given_with(
    name: str, address: str, others: list[re.Pattern[str]], pages: list[WebSearchHit]
) -> bool:
    street = _HOUSE_AND_STREET.match(_fold(address))
    if street is None:
        # A district or a landmark: no street address to hold against the pages.
        return True
    written = re.compile(rf"\b{street.group(1)}(?: \d+[a-z]?)? {re.escape(street.group(2))}\b")
    forms = _name_forms(name)
    for page in pages:
        text = _fold(f"{page.title} {page.snippet}")
        if any(form.search(_fold(page.title)) for form in forms) and written.search(text):
            return True
        for found in written.finditer(text):
            before = text[: found.start()]
            end = _last_name_end(before, forms)
            if end < 0:
                continue
            between = before[end:]
            if _STREET_ADDRESS.search(between) or any(other.search(between) for other in others):
                continue
            return True
    return False


def _without_address(row: dict[str, Any], address: str) -> dict[str, Any]:
    """The place with its address gone; a Maps link searching it now finds the name in town."""
    town = address.split(",", 1)[1].strip() if "," in address else ""
    name = str(row.get("name") or "").strip()
    url = str(row.get("url") or "").strip()
    if not url or _MAPS_LINK.match(url):
        query = f"{name}, {town}" if town else name
        url = f"https://www.google.com/maps/search/?api=1&query={quote(query)}"
    kept = {key: value for key, value in row.items() if key not in {"address", "location"}}
    return {**kept, "url": url}


def _venue_rows(body: str, lang: str) -> list[dict[str, Any]] | None:
    """The fence's places, or None when it holds none (a ```json fence of something else)."""
    try:
        parsed: object = json.loads(body.strip() or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    rows = [row for row in parsed if isinstance(row, dict)]
    named = all(isinstance(row.get("name"), str) and row["name"].strip() for row in rows)
    if lang == "json" and not (rows and len(rows) == len(parsed) and named):
        return None
    return rows


def _checked_rows(rows: list[dict[str, Any]], pages: list[WebSearchHit]) -> list[dict[str, Any]]:
    names = [_place_name(str(row.get("name") or "")) for row in rows]
    checked = []
    for row, name in zip(rows, names, strict=True):
        address = str(row.get("address") or row.get("location") or "").strip()
        others = [_mention(other) for other in names if other and other != name]
        given = not address or _given_with(str(row.get("name") or ""), address, others, pages)
        checked.append(row if given else _without_address(row, address))
    return checked


def keep_given_addresses(text: str, pages: list[WebSearchHit]) -> str:
    """Each places-list address the reply's pages give that place; the others left out."""
    if not pages or "```" not in text:
        return text
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in _LIST_LANGS:
            continue
        rows = _venue_rows(text[fence.body_start : fence.body_end], fence.lang)
        if rows is None:
            continue
        checked = _checked_rows(rows, pages)
        if checked == rows:
            continue
        payload = json.dumps(checked, ensure_ascii=False)
        newline = "\n" if text[fence.start : fence.end].endswith("\n") else ""
        pieces.append(text[cursor : fence.start])
        pieces.append(f"```{fence.lang}\n{payload}\n```{newline}")
        cursor = fence.end
    pieces.append(text[cursor:])
    return "".join(pieces)
