# ruff: noqa: E501, RUF001
"""Current expression groups — source of truth for language lessons.

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
    ipa: str | None = None
    part_of_speech: str | None = None
    simple_gloss: str | None = None
    vocabulary_kind: str = "word"
    verb_kind: str | None = None
    noun_kind: str | None = None


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


@lru_cache(maxsize=1)
def all_catalog_decks() -> tuple[CatalogDeck, ...]:
    """Only the current expression groups may be served or synchronized."""
    return tuple([*path_decks_for_language("en"), *path_decks_for_language("es")])


def decks_for_language(
    language: str,
    *,
    include_sat: bool = False,
) -> list[CatalogDeck]:
    """Current curated groups; retired beginner and SAT banks are excluded."""
    lang = (language or "en").strip().lower()
    found = [deck for deck in all_catalog_decks() if deck.language == lang]
    if not include_sat:
        found = [deck for deck in found if deck.kind != "sat"]
    if found:
        return sorted(found, key=lambda deck: deck.sort_order)
    english = [deck for deck in all_catalog_decks() if deck.language == "en"]
    if not include_sat:
        english = [deck for deck in english if deck.kind != "sat"]
    return sorted(english, key=lambda deck: deck.sort_order)


def path_decks_for_language(language: str) -> list[CatalogDeck]:
    """Decks that belong on the lesson map.

    Current groups retain their identities. Unknown codes fall back to English;
    class level never hides groups.
    """
    from app.content.learning_catalog import load_path

    lang = "es" if (language or "en").strip().lower() == "es" else "en"
    return list(load_path(lang))


def catalog_path_titles(language: str, *, include_sat: bool = False) -> list[str]:
    del include_sat
    return [deck.title for deck in path_decks_for_language(language)]


def catalog_domain_by_title(language: str, *, include_sat: bool = False) -> dict[str, str]:
    return {
        deck.title.casefold(): deck.domain
        for deck in [
            *decks_for_language(language, include_sat=include_sat),
            *path_decks_for_language(language),
        ]
    }


def catalog_domains(language: str, *, include_sat: bool = False) -> list[str]:
    decks = (
        decks_for_language(language, include_sat=True)
        if include_sat
        else path_decks_for_language(language)
    )
    seen: set[str] = set()
    out: list[str] = []
    for deck in decks:
        key = deck.domain.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(deck.domain)
    return out


def catalog_word_count(language: str, *, include_sat: bool = False) -> int:
    decks = (
        decks_for_language(language, include_sat=True)
        if include_sat
        else path_decks_for_language(language)
    )
    return sum(len(deck.words) for deck in decks)
