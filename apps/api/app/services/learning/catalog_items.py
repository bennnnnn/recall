"""Plan catalog-owned content changes without guessing from a word alone."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.content.vocab_catalog import CatalogDeck, CatalogWord, word_id

CONTENT_FIELDS = (
    "definition",
    "example_sentence",
    "ipa",
    "part_of_speech",
    "simple_gloss",
    "vocabulary_kind",
    "verb_kind",
    "noun_kind",
)


@dataclass
class CatalogChange:
    item: Any | None
    values: dict[str, Any]


def word_values(deck: CatalogDeck, word: CatalogWord) -> dict[str, Any]:
    return {
        "catalog_entry_id": word_id(deck, word),
        "content": word.content,
        "list_title": deck.title,
        **{name: getattr(word, name) for name in CONTENT_FIELDS},
    }


@lru_cache(maxsize=1)
def _legacy_fingerprints() -> frozenset[tuple[str, str, str, str | None]]:
    from app.content.vocab_banks_en import english_decks, english_path_decks
    from app.content.vocab_banks_es import spanish_decks
    from app.services.projects.common import _list_key

    return frozenset(
        (_list_key(deck.title), _list_key(word.content), word.definition, word.example_sentence)
        for deck in [*spanish_decks(), *english_decks(), *english_path_decks()]
        for word in deck.words
    )


def plan_catalog_changes(decks: Sequence[CatalogDeck], items: Sequence[Any]) -> list[CatalogChange]:
    """Preserve unrecognized user rows and every existing practice identity.

    Catalog IDs identify owned content even after a chapter title changes. A
    null-ID legacy row is adopted only with an exact old source fingerprint.
    Unknown rows occupying a canonical pair stay intact and count as present.
    """
    from app.services.projects.common import _list_key

    by_catalog: dict[Any, list[Any]] = defaultdict(list)
    pairs: dict[tuple[str, str], Any] = {}
    for item in items:
        by_catalog[getattr(item, "catalog_entry_id", None)].append(item)
        pairs.setdefault((_list_key(item.list_title), _list_key(item.content)), item)
    changes = []
    for deck in decks:
        for word in deck.words:
            values = word_values(deck, word)
            pair = (_list_key(deck.title), _list_key(word.content))
            linked = by_catalog.get(values["catalog_entry_id"], [])
            occupant = pairs.get(pair)
            if not linked and occupant is not None:
                fingerprint = (*pair, occupant.definition, occupant.example_sentence)
                if (
                    getattr(occupant, "catalog_entry_id", None) is None
                    and fingerprint in _legacy_fingerprints()
                ):
                    linked = [occupant]
                else:
                    continue
            if not linked:
                changes.append(CatalogChange(None, values))
                continue
            for item in linked:
                fields = dict(values)
                # Never merge two rows or sacrifice either row's practice history.
                if occupant is not None and occupant.id != item.id:
                    fields.pop("list_title")
                    fields.pop("content")
                else:
                    pairs[pair] = occupant = item
                if any(getattr(item, name, None) != value for name, value in fields.items()):
                    changes.append(CatalogChange(item, fields))
    return changes
