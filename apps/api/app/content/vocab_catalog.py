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


def decks_for_language(language: str) -> list[CatalogDeck]:
    lang = (language or "en").strip().lower()
    found = [deck for deck in all_catalog_decks() if deck.language == lang]
    if found:
        return sorted(found, key=lambda deck: deck.sort_order)
    english = [deck for deck in all_catalog_decks() if deck.language == "en"]
    return sorted(english, key=lambda deck: deck.sort_order)


def catalog_path_titles(language: str) -> list[str]:
    return [deck.title for deck in decks_for_language(language)]


def catalog_domain_by_title(language: str) -> dict[str, str]:
    return {deck.title.casefold(): deck.domain for deck in decks_for_language(language)}


def catalog_domains(language: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for deck in decks_for_language(language):
        key = deck.domain.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(deck.domain)
    return out


def catalog_word_count(language: str) -> int:
    return sum(len(deck.words) for deck in decks_for_language(language))


def catalog_rows() -> list[CatalogDeck]:
    return list(all_catalog_decks())
