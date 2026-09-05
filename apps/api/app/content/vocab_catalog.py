# ruff: noqa: E501, RUF001
"""Curated vocabulary banks — source of truth for language chapter words.

The model teaches from these lists only. It does not invent words.
English and Spanish only for now.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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


def _w(
    content: str,
    definition: str,
    example: str | None = None,
    *,
    example2: str | None = None,
    ipa: str | None = None,
    pos: str | None = None,
    simple: str | None = None,
) -> CatalogWord:
    examples = [part.strip() for part in (example, example2) if part and part.strip()]
    example_sentence = "\n".join(examples) if examples else None
    return CatalogWord(
        content=content,
        definition=definition,
        example_sentence=example_sentence,
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


def merge_decks_by_domain(decks: list[CatalogDeck]) -> list[CatalogDeck]:
    """One lesson-map node per domain. Keeps the first deck's slug (UUID5 identity)."""
    groups: dict[str, list[CatalogDeck]] = {}
    order: list[str] = []
    for deck in decks:
        if deck.domain not in groups:
            order.append(deck.domain)
            groups[deck.domain] = []
        groups[deck.domain].append(deck)
    merged: list[CatalogDeck] = []
    for domain in order:
        group = sorted(groups[domain], key=lambda item: item.sort_order)
        first = group[0]
        seen: set[str] = set()
        words: list[CatalogWord] = []
        for deck in group:
            for word in deck.words:
                key = word.content.casefold()
                if key in seen:
                    continue
                seen.add(key)
                words.append(word)
        merged.append(
            _deck(
                first.language,
                first.slug,
                domain,
                words,
                domain=domain,
                kind=first.kind,
                sort_order=first.sort_order,
            )
        )
    return merged


def dedupe_words_across_decks(decks: list[CatalogDeck]) -> list[CatalogDeck]:
    """First occurrence wins. Combining several curated sources into one path
    (e.g. practical topic decks + conversation-grouped decks) can repeat a
    lemma across chapters (`already` as both a time word and a discourse
    marker). Keeps deck order and each deck's own word order; only drops a
    later duplicate of a lemma already taught earlier in the sequence.
    """
    seen: set[str] = set()
    out: list[CatalogDeck] = []
    for deck in decks:
        words: list[CatalogWord] = []
        for word in deck.words:
            key = word.content.casefold()
            if key in seen:
                continue
            seen.add(key)
            words.append(word)
        out.append(replace(deck, words=tuple(words)))
    return out


@lru_cache(maxsize=1)
def all_catalog_decks() -> tuple[CatalogDeck, ...]:
    from app.content.vocab_banks_en import english_decks
    from app.content.vocab_banks_es import spanish_decks

    # Old UUIDs remain valid for saved items. Active lessons own the content
    # when their merged deck shares an ID with an older source chapter.
    by_id = {deck.id: deck for deck in [*spanish_decks(), *english_decks()]}
    for deck in [*path_decks_for_language("es"), *path_decks_for_language("en")]:
        old = by_id.get(deck.id)
        active_words = {word_id(deck, word) for word in deck.words}
        legacy_words = (
            tuple(word for word in old.words if word_id(old, word) not in active_words)
            if old
            else ()
        )
        by_id[deck.id] = replace(deck, words=(*deck.words, *legacy_words))
    return tuple(by_id.values())


def decks_for_language(
    language: str,
    *,
    include_sat: bool = False,
) -> list[CatalogDeck]:
    """All curated decks for a language. Later chapters lock in the lesson map."""
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

    Curated content preserves existing chapter/word identities and appends new
    groups. Unknown codes fall back to English; class level never hides groups.
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
