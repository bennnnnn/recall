"""Outlet names a searched reply puts in brackets after a fact: "(Experian)", "(USAGov, FTC)".

The source chips under the reply already name its sources, so a bracket that only credits
this turn's own results is noise in the sentence (2026-11-06: "payment history is about 35%
of your FICO score (Experian)"). The prompt says so, and a small model still writes them.
A bracket naming anything else stays: an aside, a number, a source this turn never had, the
short form of the name just before it ("the Federal Trade Commission (FTC)"), or a name that
is the content ("the bureaus (Equifax, Experian, TransUnion), since …").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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


# A title names its outlet after its last separator: "What Affects Your Credit Scores? -
# Experian", "5 ways to build credit | First Southwest Bank".
_TITLE_SEPARATOR = re.compile(r"\s+[|\-\u2013\u2014\u00b7:]\s+")


@dataclass(frozen=True)
class _Outlet:
    """One result's outlet: the name its title ends on, and its site's labels."""

    name: tuple[str, ...]
    site: tuple[str, ...]

    def credited_by(self, words: list[str]) -> bool:
        """The name opens the outlet's name ("Broadview" for Broadview Federal Credit
        Union), or is its site ("FTC" for consumer.ftc.gov, "USA.gov" for usa.gov). A word
        that is only somewhere in a title ("Credit") credits nothing."""
        joined = "".join(words)
        if self.name and tuple(words) == self.name[: len(words)]:
            return True
        # A site label, never its ending alone ("gov", "com").
        return joined in self.site[:-1] or joined in ("".join(self.site), "".join(self.site[:-1]))


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


def _outlets(hits: list[WebSearchHit]) -> list[_Outlet]:
    outlets = []
    for hit in hits:
        parts = _TITLE_SEPARATOR.split(hit.title.strip())
        host = (urlsplit(hit.url).hostname or "").lower().split(".")
        site = tuple(label for label in host if label and label != "www")
        outlets.append(_Outlet(_tokens(parts[-1]) if len(parts) > 1 else (), site))
    return outlets


def _credits(name: str, outlets: list[_Outlet]) -> bool:
    """``name`` is one of this turn's outlets."""
    if not _NAME.fullmatch(name) or len(name.split()) > 4:
        return False
    words = list(_tokens(name))
    return bool(words) and any(outlet.credited_by(words) for outlet in outlets)


def _spells(acronym: str, before: str) -> bool:
    """``acronym`` is the initials of the words just before it: "Federal Trade Commission
    (FTC)" defines a short form the reply may use again."""
    if not acronym.isupper() or not acronym.isalpha():
        return False
    initials = "".join(word[0] for word in _WORD.findall(before)[-len(acronym) :])
    return initials.upper() == acronym


# A credit closes a claim: the sentence or line ends after it ("… 35% of your score
# (Experian)."). A bracket going on into the sentence ("the bureaus (Equifax, Experian,
# TransUnion), since …", "the Fed (Federal Reserve) raised") is the content.
_CLOSES = re.compile(r"[*_]*(?:[.;!?]|[^\S\n]*(?:\n|$))")
# … and one right after "the company" or "a bank" names the thing just said.
_NAMES_THE_THING = re.compile(
    r"\b(?:the|a|an|this|that|these|those)(?:\s+[\w'-]+){1,2}[*_]*$", re.I
)


def _is_credit(prose: str, match: re.Match[str]) -> bool:
    before = prose[: match.start()]
    return bool(_CLOSES.match(prose, match.end())) and not _NAMES_THE_THING.search(before)


def _drop_credits(prose: str, outlets: list[_Outlet]) -> str:
    def drop(match: re.Match[str]) -> str:
        names = [name for name in _SEPARATOR.split(match.group(1).strip()) if name]
        if not _is_credit(prose, match):
            return match.group(0)
        if len(names) == 1 and _spells(names[0], prose[: match.start()]):
            return match.group(0)
        return "" if names and all(_credits(name, outlets) for name in names) else match.group(0)

    return _BRACKET.sub(drop, prose)


def drop_source_credits(text: str, hits: list[WebSearchHit]) -> str:
    """``text`` without the brackets that only name this turn's own sources; a fence's
    content is left as written."""
    outlets = _outlets(hits)
    if not outlets:
        return text
    return map_outside_fences(text, lambda prose: _drop_credits(prose, outlets))
