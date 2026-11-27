"""Where a name the reply links opens, decided by the server, never by the model's address.

"We need a link to any name that needs a user to check" (the owner, 2026-11-27): a reply
listed six San Francisco restaurants as bold names with nothing to tap. The reply's model
marks each name it recommends, ``[Zuni Café](check "San Francisco")`` (``NAME_LINK_RULE``),
and the server picks where it goes:

1. its own site, when one of this turn's search results is on a host that names it
   (zunicafe.com for Zuni Café): an address the search found, not one the model wrote;
2. else, for a place someone can visit (the model gave its city), a Google Maps search for
   the name and the city;
3. else a Google search for the name.

The phone opens a name the same way while the reply streams (``lib/markdown/replyLinks.ts``);
``docs/fixtures/name_links.json`` holds the two to the same addresses.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import quote, urlsplit

MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query="
WEB_SEARCH = "https://www.google.com/search?q="
# What encodeURIComponent leaves as it is, so the phone's twin writes the same address.
_URI_SAFE = "!~*'()"
# Markdown a link's words may carry: **bold**, *italic*, `code`.
_EMPHASIS = re.compile(r"[*_`]+")
# Past this many words a link's words are a sentence, not a name.
_NAME_WORDS_MAX = 8
_NAME_CHARS_MAX = 80
# A host's label naming the thing may add this much ("nopasf" for Nopa).
_HOST_SUFFIX_MAX = 3
# A name folded this short is matched only by a host label equal to it ("cs50").
_PREFIX_NAME_MIN = 4
_FOLDED_NAME_MIN = 3
# Second-level labels of country domains (example.co.uk): no part of a name.
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})


class Page(Protocol):
    """A search result the reply's turn found (``WebSearchHit``)."""

    @property
    def url(self) -> str: ...


def maps_search_url(query: str) -> str:
    return MAPS_SEARCH + quote(query.strip(), safe=_URI_SAFE)


def web_search_url(query: str) -> str:
    return WEB_SEARCH + quote(query.strip(), safe=_URI_SAFE)


def name_text(words: str) -> str:
    """A link's words as the name they say: no emphasis marks, one space between words."""
    return " ".join(_EMPHASIS.sub("", words).split())


def is_a_name(words: str) -> bool:
    """Words that can name a thing to look up: a capital or a digit in a script with case
    ("Zuni Café", "iPhone 16", "CS50"), not a kind of thing ("a taqueria") or a sentence."""
    text = name_text(words)
    if not text or len(text) > _NAME_CHARS_MAX or len(text.split()) > _NAME_WORDS_MAX:
        return False
    if not any(char.isalnum() for char in text):
        return False
    cased = [char for char in text if char.lower() != char.upper()]
    return not cased or any(char.isupper() or char.isdigit() for char in text)


def _fold(name: str) -> str:
    """The name as a host spells it: "The House of Prime Rib" is "houseofprimerib"."""
    plain = unicodedata.normalize("NFKD", name.casefold().replace("&", " and "))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    plain = re.sub(r"^\s*the\s+", "", plain)
    return re.sub(r"[^a-z0-9]", "", plain)


def _name_labels(host: str) -> list[str]:
    """The labels of ``host`` that can name a thing: not ``www``, the top-level domain or a
    country domain's second level."""
    labels = [label for label in host.lower().split(".") if label and label != "www"]
    labels = labels[:-1]
    if len(labels) >= 2 and labels[-1] in _SECOND_LEVEL:
        labels = labels[:-1]
    return labels


def _names(label: str, folded: str) -> bool:
    if label == folded:
        return True
    return (
        len(folded) >= _PREFIX_NAME_MIN
        and label.startswith(folded)
        and len(label) - len(folded) <= _HOST_SUFFIX_MAX
    )


def own_site(name: str, pages: Sequence[Page]) -> str | None:
    """The home page of a search result whose host names ``name``, or None."""
    folded = _fold(name)
    if len(folded) < _FOLDED_NAME_MIN:
        return None
    for page in pages:
        try:
            parts = urlsplit(page.url.strip())
        except ValueError:
            continue
        host = parts.hostname
        if parts.scheme.lower() not in {"http", "https"} or not host:
            continue
        if any(_names(label, folded) for label in _name_labels(host)):
            return f"https://{host}/"
    return None


def name_target(name: str, city: str, pages: Sequence[Page]) -> str:
    """Where the linked ``name`` opens: its own site, Maps for a place, or a search."""
    site = own_site(name, pages)
    if site is not None:
        return site
    if city:
        return maps_search_url(f"{name}, {city}")
    return web_search_url(name)
