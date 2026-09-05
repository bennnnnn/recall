"""Plan catalog-owned content changes without guessing from a word alone."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

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


_Item = TypeVar("_Item")


def active_catalog_items(decks: Sequence[CatalogDeck], items: Sequence[_Item]) -> list[_Item]:
    """Only explicit current catalog identities survive content retirement."""
    active_ids = {word_id(deck, word) for deck in decks for word in deck.words}
    return [item for item in items if getattr(item, "catalog_entry_id", None) in active_ids]


def plan_catalog_changes(decks: Sequence[CatalogDeck], items: Sequence[Any]) -> list[CatalogChange]:
    """Refresh current identities; never adopt retired or unrecognized rows."""
    from app.services.projects.common import _list_key

    by_catalog: dict[Any, list[Any]] = defaultdict(list)
    pairs: dict[tuple[str, str], Any] = {}
    for item in active_catalog_items(decks, items):
        by_catalog[getattr(item, "catalog_entry_id", None)].append(item)
        pairs.setdefault((_list_key(item.list_title), _list_key(item.content)), item)
    changes = []
    for deck in decks:
        for word in deck.words:
            values = word_values(deck, word)
            pair = (_list_key(deck.title), _list_key(word.content))
            linked = by_catalog.get(values["catalog_entry_id"], [])
            occupant = pairs.get(pair)
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
