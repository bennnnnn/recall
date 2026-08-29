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
    ipa: str | None = None
    part_of_speech: str | None = None
    simple_gloss: str | None = None


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


def _w(
    content: str,
    definition: str,
    example: str | None = None,
    *,
    ipa: str | None = None,
    pos: str | None = None,
    simple: str | None = None,
) -> CatalogWord:
    return CatalogWord(
        content=content,
        definition=definition,
        example_sentence=example,
        ipa=ipa,
        part_of_speech=pos,
        simple_gloss=simple,
    )


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
) -> list[CatalogDeck]:
    """All curated decks for a language. Later chapters lock in the lesson map;
    they are not hidden by class level.
    """
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

    English uses the conversation-grouped path (not Hotel/SAT). Spanish keeps
    the existing domain tree. Unknown codes fall back to the English path.
    Class level does not hide later groups.
    """
    lang = (language or "en").strip().lower()
    if lang == "es":
        return decks_for_language("es", include_sat=False)
    from app.content.vocab_banks_en import english_path_decks

    return sorted(english_path_decks(), key=lambda deck: deck.sort_order)


def catalog_path_titles(language: str, *, include_sat: bool = False) -> list[str]:
    del include_sat
    return [deck.title for deck in path_decks_for_language(language)]


def catalog_domain_by_title(language: str, *, include_sat: bool = False) -> dict[str, str]:
    return {
        deck.title.casefold(): deck.domain
        for deck in decks_for_language(language, include_sat=include_sat)
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


def catalog_rows() -> list[CatalogDeck]:
    return list(all_catalog_decks())
