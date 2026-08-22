# ruff: noqa: E501, RUF001
"""Curated vocabulary banks — source of truth for language chapter words.

The model teaches from these lists only. It does not invent words.
English and Spanish only for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from uuid import UUID, uuid5

CATALOG_NS = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

DeckKind = Literal["chapter", "sat"]


@dataclass(frozen=True)
class CatalogWord:
    content: str
    definition: str
    example_sentence: str | None = None


@dataclass(frozen=True)
class CatalogDeck:
    language: str
    slug: str
    title: str
    domain: str
    kind: DeckKind
    words: tuple[CatalogWord, ...]
    sort_order: int

    @property
    def id(self) -> UUID:
        return uuid5(CATALOG_NS, f"deck:{self.language}:{self.slug}")


def word_id(deck: CatalogDeck, word: CatalogWord) -> UUID:
    return uuid5(CATALOG_NS, f"word:{deck.language}:{deck.slug}:{word.content.casefold()}")


def _w(content: str, definition: str, example: str | None = None) -> CatalogWord:
    return CatalogWord(content=content, definition=definition, example_sentence=example)


def _deck(
    language: str,
    slug: str,
    title: str,
    words: list[CatalogWord],
    *,
    domain: str,
    kind: DeckKind = "chapter",
    sort_order: int,
) -> CatalogDeck:
    return CatalogDeck(
        language=language,
        slug=slug,
        title=title,
        domain=domain,
        kind=kind,
        words=tuple(words),
        sort_order=sort_order,
    )


@lru_cache(maxsize=1)
def all_catalog_decks() -> tuple[CatalogDeck, ...]:
    from app.content.vocab_banks_en import english_decks
    from app.content.vocab_banks_es import spanish_decks

    return tuple([*spanish_decks(), *english_decks()])


# Minimum level (1=beginner … 6=fluent) at which each domain's decks become
# available. A level-N project sees decks from domains with min_level <= N.
_DOMAIN_MIN_LEVEL: dict[str, int] = {
    "Greetings": 1,
    "Numbers and time": 1,
    "Family": 2,
    "Food": 3,
    "Home": 3,
    "Hotel": 4,
    "Travel": 4,
    "Daily life": 5,
    "SAT": 6,
}


def _domain_min_level(domain: str) -> int:
    return _DOMAIN_MIN_LEVEL.get(domain, 1)


def level_to_int(level: str | None) -> int:
    """Convert 'level3' → 3; unknown/missing → 1 (beginner-safe default)."""
    if not isinstance(level, str):
        return 1
    digits = level.removeprefix("level").strip()
    n = int(digits) if digits.isdigit() else 1
    return max(1, min(6, n))


def decks_for_language(
    language: str,
    *,
    include_sat: bool = False,
    level: int = 6,
) -> list[CatalogDeck]:
    lang = (language or "en").strip().lower()
    found = [deck for deck in all_catalog_decks() if deck.language == lang]
    if not include_sat:
        found = [deck for deck in found if deck.kind != "sat"]
    if level < 6:
        found = [deck for deck in found if _domain_min_level(deck.domain) <= level]
    if found:
        return sorted(found, key=lambda deck: deck.sort_order)
    english = [deck for deck in all_catalog_decks() if deck.language == "en"]
    if not include_sat:
        english = [deck for deck in english if deck.kind != "sat"]
    if level < 6:
        english = [deck for deck in english if _domain_min_level(deck.domain) <= level]
    return sorted(english, key=lambda deck: deck.sort_order)


def catalog_path_titles(language: str, *, include_sat: bool = False, level: int = 6) -> list[str]:
    return [
        deck.title for deck in decks_for_language(language, include_sat=include_sat, level=level)
    ]


def catalog_domain_by_title(
    language: str, *, include_sat: bool = False, level: int = 6
) -> dict[str, str]:
    return {
        deck.title.casefold(): deck.domain
        for deck in decks_for_language(language, include_sat=include_sat, level=level)
    }


def catalog_domains(language: str, *, include_sat: bool = False, level: int = 6) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for deck in decks_for_language(language, include_sat=include_sat, level=level):
        key = deck.domain.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(deck.domain)
    return out


def catalog_word_count(language: str, *, level: int = 6) -> int:
    return sum(len(deck.words) for deck in decks_for_language(language, level=level))


def catalog_rows() -> list[CatalogDeck]:
    return list(all_catalog_decks())
