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
    """Insert any catalog decks/words missing from the DB. Existing rows stay."""
    decks = all_catalog_decks()
    if not decks:
        return
    deck_rows = [
        {
            "id": deck.id,
            "target_language": deck.language,
            "slug": deck.slug,
            "title": deck.title,
            "domain": deck.domain,
            "kind": deck.kind,
            "sort_order": deck.sort_order,
        }
        for deck in decks
    ]
    await _insert_ignore(session, VocabDeck, deck_rows)
    entry_rows = [
        {
            "id": word_id(deck, word),
            "deck_id": deck.id,
            "content": word.content,
            "definition": word.definition,
            "example_sentence": word.example_sentence,
            "sort_order": index,
        }
        for deck in decks
        for index, word in enumerate(deck.words)
    ]
    await _insert_ignore(session, VocabEntry, entry_rows)
    await session.flush()


async def _insert_ignore(
    session: AsyncSession,
    table: type[Any],
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    for offset in range(0, len(rows), _CHUNK):
        chunk = rows[offset : offset + _CHUNK]
        await session.execute(pg_insert(table).values(chunk).on_conflict_do_nothing())
