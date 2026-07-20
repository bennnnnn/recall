from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.repositories import memories as memories_repo


@pytest.fixture
def fake_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_upsert_sections_empty_items_is_noop(fake_session):
    await memories_repo.upsert_sections(fake_session, user_id=uuid4(), items=[])
    fake_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_sections_executes_and_commits(fake_session):
    user_id = uuid4()
    items = [("profile", "User is Sam, a software engineer.", 0.9, None)]
    await memories_repo.upsert_sections(fake_session, user_id=user_id, items=items)
    fake_session.execute.assert_awaited_once()
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_sections_deduplicates_duplicate_types(fake_session):
    """Two sections with the same type would make Postgres raise
    'ON CONFLICT DO UPDATE cannot affect row a second time'. The repo must
    dedupe by type, keeping the highest-confidence section."""
    user_id = uuid4()
    items = [
        ("profile", "Low confidence profile.", 0.5, None),
        ("profile", "High confidence profile.", 0.9, None),
        ("preference", "Likes tea.", 0.8, None),
    ]
    captured: dict[str, list] = {}

    def fake_pg_insert(_table):
        stmt = MagicMock()

        def values(rows):
            captured["rows"] = rows
            stmt.excluded = MagicMock()
            return stmt

        stmt.values = values
        stmt.on_conflict_do_update.return_value = stmt
        return stmt

    with patch("app.repositories.memories.pg_insert", side_effect=fake_pg_insert):
        await memories_repo.upsert_sections(fake_session, user_id=user_id, items=items)

    types = [r["type"] for r in captured["rows"]]
    assert sorted(types) == ["preference", "profile"]
    profile_row = next(r for r in captured["rows"] if r["type"] == "profile")
    assert profile_row["text"] == "High confidence profile."
    assert profile_row["confidence"] == 0.9


@pytest.mark.asyncio
async def test_upsert_sections_duplicate_type_ties_break_to_later_item(fake_session):
    """Equal confidence → the later item wins (last-writer semantics)."""
    user_id = uuid4()
    items = [
        ("fact", "First fact.", 0.7, None),
        ("fact", "Second fact.", 0.7, None),
    ]
    captured: dict[str, list] = {}

    def fake_pg_insert(_table):
        stmt = MagicMock()

        def values(rows):
            captured["rows"] = rows
            stmt.excluded = MagicMock()
            return stmt

        stmt.values = values
        stmt.on_conflict_do_update.return_value = stmt
        return stmt

    with patch("app.repositories.memories.pg_insert", side_effect=fake_pg_insert):
        await memories_repo.upsert_sections(fake_session, user_id=user_id, items=items)

    assert len(captured["rows"]) == 1
    assert captured["rows"][0]["text"] == "Second fact."


@pytest.mark.asyncio
async def test_list_for_user_returns_memories(fake_session):
    user_id = uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    fake_session.execute.return_value = mock_result
    result = await memories_repo.list_for_user(fake_session, user_id)
    assert result == []


@pytest.mark.asyncio
async def test_has_any_embedding_true_when_row_exists(fake_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid4()
    fake_session.execute.return_value = mock_result
    assert await memories_repo.has_any_embedding(fake_session, uuid4()) is True


@pytest.mark.asyncio
async def test_has_any_embedding_false_when_empty(fake_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    fake_session.execute.return_value = mock_result
    assert await memories_repo.has_any_embedding(fake_session, uuid4()) is False
