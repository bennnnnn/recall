"""A places list's addresses, kept to the ones the reply's pages give each place.

A list article names many places and many addresses. The card put Copra, "Indian,
Japantown", at 725 Columbus Avenue in North Beach, an address the same article gave
another restaurant (2026-11-08). A page gives a place its address when it writes it after
the place's name, within a stretch that ends at the next entry: another street address,
another place on the card, a numbered entry ("3. Lunette."), a sentence that gives the
address to another name ("Tosca Cafe sits at 242 Columbus Ave"), or, as a backstop, a long
run of text. A directory line that writes the address first ("600 Guerrero St — Tartine
Bakery") gives it too, and so does the place's own page anywhere (its name in the title,
where Yelp also writes the address). Any other address leaves the list, and a Maps link
built on it then finds the place by name in its town. A venue list the model fenced as
```json is drawn by the phone as a places list, so it is checked too, but only its
addresses change: the JSON keeps its other fields and layout, and a turn that asked for
JSON keeps it as written.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import quote

from app.gateways.web_search_gateway import WebSearchHit
from app.services.md_fence_scan import Fence, iter_fences

_LIST_LANGS = frozenset({"places", "json"})
# A name's first word this long stands for it ("Franciscan" for "Franciscan Crab Restaurant").
_NAME_WORD_MIN = 5
# Past this many characters after a place's name, an address belongs to a later entry.
_AFTER_NAME_MAX = 600
# A house number (or a range of them, "1658-1660") and the street's first word ("18th").
_HOUSE_AND_STREET = re.compile(r"^(\d+[a-z]?)(?: \d+(?= ))? ([a-z0-9]+)", re.IGNORECASE)
# Any street address in folded text: a house number, a few words naming the street, and a
# street word. "2 blocks from Dolores St" is a distance to a street, not an address.
_STREET_ADDRESS = re.compile(
    r"\b\d+[a-z]?(?: \d+(?= ))? "
    r"(?:(?!(?:from|to|of|off|near|at|past|away|blocks?|miles?|minutes?|mins?|km|meters?"
    r"|metres?|feet|ft|steps?|walk)\b)[a-z0-9]+ ){1,4}?"
    r"(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|way|pl|place|ct|court"
    r"|sq|square|pkwy|parkway|hwy|highway|plaza|building|bldg)\b",
    re.IGNORECASE,
)
# A numbered entry of a list: ". 3 . Lunette" in folded text.
_LIST_ENTRY = re.compile(r"(?:^|\. )\d{1,2} \. [A-Z]")
# A sentence that gives the address to a name: "Tosca Cafe sits at 242 Columbus Ave".
_GIVEN_TO = re.compile(
    r"^(?P<subject>[A-Z][A-Za-z0-9']*(?: [A-Z][A-Za-z0-9']*)*)"
    r"(?: (?:is|sits|stands|lies|is located|located|can be found))?(?: (?:at|on|in))?$"
)
# A Maps link searches the address it was written with; a venue's own site does not.
_MAPS_LINK = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*(?:google\.[a-z.]+/maps|maps\.google\.[a-z.]+/"
    r"|goo\.gl/maps|maps\.app\.goo\.gl/)",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    """Accents dropped and case kept, a sentence's end kept as " . " and every other run of
    characters one space: "3. Lunette. Cambodian street food." is no "3 … Street"."""
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    plain = re.sub(r"[.!?;:\n]+", " . ", plain)
    return " ".join(re.sub(r"[^A-Za-z0-9.]+", " ", plain).split())


def _place_name(name: str) -> str:
    """The name as pages write it: "The Slanted Door" is often "Slanted Door"."""
    return re.sub(r"^the ", "", _fold(name), flags=re.IGNORECASE).lower()


def _mention(form: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(form)}\b", re.IGNORECASE)


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


def _another_entry(between: str, others: list[re.Pattern[str]]) -> bool:
    """Something between a name and an address that starts another entry."""
    return (
        len(between) > _AFTER_NAME_MAX
        or _STREET_ADDRESS.search(between) is not None
        or _LIST_ENTRY.search(between) is not None
        or any(other.search(between) for other in others)
    )


def _given_to_another(sentence: str, forms: list[re.Pattern[str]]) -> bool:
    """The address's own sentence gives it to a name that is not this place."""
    found = _GIVEN_TO.match(sentence.strip())
    return found is not None and not any(form.search(found["subject"]) for form in forms)


def _written_for(
    text: str, address: re.Match[str], forms: list[re.Pattern[str]], others: list[re.Pattern[str]]
) -> bool:
    """This occurrence of the address is the place's: after its name in the same entry, or
    first on a directory line that names it next."""
    before = text[: address.start()]
    sentence = before[before.rfind(" . ") + 3 :] if " . " in before else before
    if _given_to_another(sentence, forms):
        return False
    end = _last_name_end(before, forms)
    if end >= 0 and not _another_entry(before[end:], others):
        return True
    after = text[address.end() :].split(" . ", 1)[0]
    named = _last_name_end(after, forms)
    return named >= 0 and _STREET_ADDRESS.search(after[:named]) is None


def _given_with(
    name: str, address: str, others: list[re.Pattern[str]], pages: list[WebSearchHit]
) -> bool:
    street = _HOUSE_AND_STREET.match(_fold(address))
    if street is None:
        # A district or a landmark: no street address to hold against the pages.
        return True
    written = re.compile(
        rf"\b{street.group(1)}(?: \d+(?= ))? {re.escape(street.group(2))}\b", re.IGNORECASE
    )
    forms = _name_forms(name)
    for page in pages:
        text = _fold(f"{page.title} . {page.snippet}")
        if any(form.search(_fold(page.title)) for form in forms) and written.search(text):
            return True
        if any(_written_for(text, found, forms, others) for found in written.finditer(text)):
            return True
    return False


def _without_address(row: dict[str, Any], address: str, *, relink: bool) -> dict[str, Any]:
    """The place with its address gone. On a places card, a Maps link that searched the
    address now finds the name in its town; a ```json body gains nothing."""
    kept = {key: value for key, value in row.items() if key not in {"address", "location"}}
    url = str(row.get("url") or "").strip()
    if not relink or (url and not _MAPS_LINK.match(url)):
        return kept
    town = address.split(",", 1)[1].strip() if "," in address else ""
    name = str(row.get("name") or "").strip()
    query = f"{name}, {town}" if town else name
    return {**kept, "url": f"https://www.google.com/maps/search/?api=1&query={quote(query)}"}


def _venue_rows(body: str, lang: str) -> list[dict[str, Any]] | None:
    """The fence's places, or None when it holds none. A ```json body counts only as the
    phone draws it as places: a list whose every entry has a name."""
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


def _checked_rows(
    rows: list[dict[str, Any]], pages: list[WebSearchHit], *, relink: bool
) -> list[dict[str, Any]]:
    names = [_place_name(str(row.get("name") or "")) for row in rows]
    checked = []
    for row, name in zip(rows, names, strict=True):
        address = str(row.get("address") or row.get("location") or "").strip()
        others = [_mention(other) for other in names if other and other != name]
        given = not address or _given_with(str(row.get("name") or ""), address, others, pages)
        checked.append(row if given else _without_address(row, address, relink=relink))
    return checked


def _checked_fence(text: str, fence: Fence, pages: list[WebSearchHit]) -> str | None:
    body = text[fence.body_start : fence.body_end]
    rows = _venue_rows(body, fence.lang)
    if rows is None:
        return None
    card = fence.lang == "places"
    checked = _checked_rows(rows, pages, relink=card)
    if checked == rows:
        return None
    # A ```json body keeps its layout: one indented over lines stays so.
    indent = None if card or "\n" not in body.strip() else 2
    payload = json.dumps(checked, ensure_ascii=False, indent=indent)
    newline = "\n" if text[fence.start : fence.end].endswith("\n") else ""
    return f"```{fence.lang}\n{payload}\n```{newline}"


def keep_given_addresses(text: str, pages: list[WebSearchHit], *, json_asked: bool = False) -> str:
    """Each places-list address the reply's pages give that place; the others left out.

    ``json_asked``: the user asked for JSON, so a ```json body is theirs, kept as written."""
    if not pages or "```" not in text:
        return text
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in _LIST_LANGS:
            continue
        if fence.lang == "json" and json_asked:
            continue
        checked = _checked_fence(text, fence, pages)
        if checked is None:
            continue
        pieces.append(text[cursor : fence.start])
        pieces.append(checked)
        cursor = fence.end
    pieces.append(text[cursor:])
    return "".join(pieces)
