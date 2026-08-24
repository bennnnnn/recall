"""Postgres tests: catalog upsert fills vocab_entries the Python catalog added."""

import pytest
from sqlalchemy import delete

from app.content.vocab_catalog import all_catalog_decks, word_id
from app.models.orm import VocabEntry
from app.services.learning.catalog_sync import ensure_catalog_rows


@pytest.mark.asyncio
async def test_ensure_catalog_rows_inserts_missing_entry(db_session):
    decks = all_catalog_decks()
    deck = next(d for d in decks if d.language == "es")
    word = deck.words[0]
    entry_id = word_id(deck, word)

    await db_session.execute(delete(VocabEntry).where(VocabEntry.id == entry_id))
    await db_session.flush()
    assert await db_session.get(VocabEntry, entry_id) is None

    await ensure_catalog_rows(db_session)
    await db_session.flush()

    row = await db_session.get(VocabEntry, entry_id)
    assert row is not None
    assert row.content == word.content


@pytest.mark.asyncio
async def test_ensure_catalog_rows_is_idempotent(db_session):
    await ensure_catalog_rows(db_session)
    await ensure_catalog_rows(db_session)
    await db_session.flush()

    decks = all_catalog_decks()
    deck = next(d for d in decks if d.language == "es")
    word = deck.words[0]
    row = await db_session.get(VocabEntry, word_id(deck, word))
    assert row is not None
    assert row.content == word.content
