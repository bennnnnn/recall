"""Keep vocab_decks / vocab_entries in sync with the Python catalog.

Language path seed writes project_items.catalog_entry_id from word_id().
Those UUIDs must already exist in vocab_entries. Alembic only refreshes the
tables when a migration wipes them, so new catalog words 500 the Learning
detail screen until we upsert here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.vocab_catalog import all_catalog_decks, word_id
from app.models.orm import VocabDeck, VocabEntry

_CHUNK = 500


async def ensure_catalog_rows(session: AsyncSession) -> None:
    """Upsert catalog-owned content without replacing referenced row identities."""
    decks = _sync_decks()
    if not decks:
        return
    deck_rows: list[dict[str, Any]] = []
    seen_decks: set[Any] = set()
    for deck in decks:
        if deck.id in seen_decks:
            continue
        seen_decks.add(deck.id)
        deck_rows.append(
            {
                "id": deck.id,
                "target_language": deck.language,
                "slug": deck.slug,
                "title": deck.title,
                "domain": deck.domain,
                "kind": deck.kind,
                "sort_order": deck.sort_order,
            }
        )
    await _upsert_content(session, VocabDeck, deck_rows)
    entry_rows: list[dict[str, Any]] = []
    seen_words: set[Any] = set()
    for deck in decks:
        for index, word in enumerate(deck.words):
            entry_id = word_id(deck, word)
            if entry_id in seen_words:
                continue
            seen_words.add(entry_id)
            entry_rows.append(
                {
                    "id": entry_id,
                    "deck_id": deck.id,
                    "content": word.content,
                    "definition": word.definition,
                    "example_sentence": word.example_sentence,
                    "ipa": word.ipa,
                    "part_of_speech": word.part_of_speech,
                    "simple_gloss": word.simple_gloss,
                    "vocabulary_kind": word.vocabulary_kind,
                    "verb_kind": word.verb_kind,
                    "noun_kind": word.noun_kind,
                    "sort_order": index,
                }
            )
    await _upsert_content(session, VocabEntry, entry_rows)
    await session.flush()


def _sync_decks() -> list[Any]:
    """Never reinsert retired source-bank rows during catalog reconciliation."""
    return list(all_catalog_decks())


async def _upsert_content(
    session: AsyncSession,
    table: type[Any],
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    for offset in range(0, len(rows), _CHUNK):
        chunk = rows[offset : offset + _CHUNK]
        statement = pg_insert(table).values(chunk)
        values = {key: getattr(statement.excluded, key) for key in chunk[0] if key != "id"}
        await session.execute(statement.on_conflict_do_update(index_elements=["id"], set_=values))
