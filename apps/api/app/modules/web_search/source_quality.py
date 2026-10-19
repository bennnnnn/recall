"""Put trustworthy sources first: a stable sort of search hits by where they come from.

Three tiers, decided by the hit's host alone. Official and reference sites
(government, education, international bodies, encyclopaedias, wire services,
journals, a product's own docs) come first; question farms, homework-answer
sites and social posts come last; everything else keeps the provider's order
in between. The model reads the hits in this order and the source chips show
them so, so an official page is the one it grounds on when one was found.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.gateways.web_search_gateway import WebSearchHit

_OFFICIAL, _ORDINARY, _WEAK = 0, 1, 2

# A host ending in one of these labels is a government, school or treaty body.
_OFFICIAL_SUFFIXES = (".gov", ".mil", ".edu", ".int")
# ".gov.uk", ".ac.uk", ".edu.au", ".go.ke": an official second-level label.
_OFFICIAL_SECOND_LEVEL = frozenset({"gov", "gob", "gouv", "go", "govt", "edu", "ac", "mil"})
_REFERENCE = frozenset(
    {
        "wikipedia.org",
        "britannica.com",
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "bbc.co.uk",
        "nature.com",
        "science.org",
        "who.int",
        "un.org",
        "europa.eu",
        "worldbank.org",
        "imf.org",
        "oecd.org",
        "python.org",
        "mozilla.org",
        "w3.org",
        "ietf.org",
        "arxiv.org",
        "pubmed.ncbi.nlm.nih.gov",
    }
)
# A product's own documentation: docs.example.com, developer.apple.com. Shared
# Google documents are anybody's writing, not documentation.
_DOCS_LABELS = frozenset({"docs", "developer", "developers", "learn", "support"})
_USER_DOCS = frozenset({"docs.google.com"})
_WEAK_SITES = frozenset(
    {
        "quora.com",
        "answers.com",
        "brainly.com",
        "chegg.com",
        "coursehero.com",
        "scribd.com",
        "pinterest.com",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "x.com",
        "twitter.com",
    }
)


def _host(url: str) -> str:
    try:
        host = urlsplit(url.strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def _on(host: str, sites: frozenset[str]) -> bool:
    """``host`` is one of ``sites`` or a subdomain of one."""
    return any(host == site or host.endswith(f".{site}") for site in sites)


def source_tier(url: str) -> int:
    """0 official or reference, 1 ordinary, 2 weak."""
    host = _host(url)
    if not host:
        return _ORDINARY
    labels = host.split(".")
    if host.endswith(_OFFICIAL_SUFFIXES) or _on(host, _REFERENCE):
        return _OFFICIAL
    country = len(labels) >= 2 and len(labels[-1]) == 2
    if country and labels[-2] in _OFFICIAL_SECOND_LEVEL:
        return _OFFICIAL
    if len(labels) >= 3 and labels[0] in _DOCS_LABELS and host not in _USER_DOCS:
        return _OFFICIAL
    if _on(host, _WEAK_SITES):
        return _WEAK
    return _ORDINARY


def rank_by_source(hits: list[WebSearchHit]) -> list[WebSearchHit]:
    """Hits with official and reference sources first; ties keep the provider's order."""
    return sorted(hits, key=lambda hit: source_tier(hit.url))
