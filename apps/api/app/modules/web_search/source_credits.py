"""Outlet names a searched reply puts in brackets after a fact: "(Experian)", "(USAGov, FTC)".

The source chips under the reply already name its sources, so a bracket that only credits
this turn's own results is noise in the sentence (2026-11-06: "payment history is about 35%
of your FICO score (Experian)"). The prompt says so, and a small model still writes them.
A bracket naming anything else stays: an aside, a number, a source this turn never had, or
the short form of the name just before it ("the Federal Trade Commission (FTC)").
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.services.answer_fence import map_outside_fences

if TYPE_CHECKING:
    from app.gateways.web_search_gateway import WebSearchHit

_BRACKET = re.compile(r"[^\S\n]*\(([^()\n]{2,80})\)")
_SEPARATOR = re.compile(r"\s*(?:[,;/&]|\band\b)\s*")
# A name: it starts with a capital and holds no digits ("Experian", "USA.gov", "First
# Southwest Bank"); "about 35%" and "e.g. rent" are asides.
_NAME = re.compile(r"[A-Z][^\d]*")
_WORD = re.compile(r"[A-Za-z][A-Za-z.'-]*")


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _source_keys(hits: list[WebSearchHit]) -> list[str]:
    """Each result's title and site, squashed: "Credit Scores | Consumer Advice
    consumerftcgov"."""
    return [f"{_squash(hit.title)} {_squash(urlsplit(hit.url).hostname or '')}" for hit in hits]


def _credits(name: str, keys: list[str]) -> bool:
    """Every word of ``name`` is in one result's title or site."""
    if not _NAME.fullmatch(name) or len(name.split()) > 4:
        return False
    words = [_squash(word) for word in _WORD.findall(name)]
    words = [word for word in words if word]
    return bool(words) and any(all(word in key for word in words) for key in keys)


def _spells(acronym: str, before: str) -> bool:
    """``acronym`` is the initials of the words just before it: "Federal Trade Commission
    (FTC)" defines a short form the reply may use again."""
    if not acronym.isupper() or not acronym.isalpha():
        return False
    initials = "".join(word[0] for word in _WORD.findall(before)[-len(acronym) :])
    return initials.upper() == acronym


def _drop_credits(prose: str, keys: list[str]) -> str:
    def drop(match: re.Match[str]) -> str:
        names = [name for name in _SEPARATOR.split(match.group(1).strip()) if name]
        if len(names) == 1 and _spells(names[0], prose[: match.start()]):
            return match.group(0)
        return "" if names and all(_credits(name, keys) for name in names) else match.group(0)

    return _BRACKET.sub(drop, prose)


def drop_source_credits(text: str, hits: list[WebSearchHit]) -> str:
    """``text`` without the brackets that only name this turn's own sources; a fence's
    content is left as written."""
    keys = _source_keys(hits)
    if not keys:
        return text
    return map_outside_fences(text, lambda prose: _drop_credits(prose, keys))
