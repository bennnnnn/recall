"""Tests for app.repositories.project_items."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import project_items as repo


def test_pos_list_title_plural_and_singular():
    assert repo.pos_list_title("noun") == "nouns"
    assert repo.pos_list_title("nouns") == "nouns"
    assert repo.pos_list_title("NOUN") == "nouns"
    assert repo.pos_list_title(None) == "other"
    assert repo.pos_list_title("custom") == "customs"


def test_normalize_pos_key():
    assert repo.normalize_pos_key("Noun") == "noun"
    assert repo.normalize_pos_key("verbs") == "verb"
    assert repo.normalize_pos_key(None) == "other"


def _item(
    *,
    content: str = "hello",
    part_of_speech: str | None = "noun",
    list_title: str = "nouns",
    status: str | None = "new",
    mastered: bool = False,
    created_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
):
    item = MagicMock()
    item.content = content
    item.part_of_speech = part_of_speech
    item.list_title = list_title
    item.status = status
    item.mastered = mastered
    item.mastered_at = None
    item.created_at = created_at or datetime.now(UTC)
    item.last_reviewed_at = last_reviewed_at
    return item


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_for_user_returns_items(fake_session):
    mock_item = _item()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_item]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await repo.list_for_user(fake_session, uuid4(), project_id=uuid4())

    assert result == [mock_item]


@pytest.mark.asyncio
async def test_get_by_id_returns_item(fake_session):
    mock_item = _item()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    fake_session.execute.return_value = mock_result

    result = await repo.get_by_id(fake_session, uuid4(), uuid4())

    assert result is mock_item


@pytest.mark.asyncio
async def test_count_stats_aggregates_statuses(fake_session):
    project_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)
    items = [
        _item(status="new", created_at=now),
        _item(status="learning", created_at=now - timedelta(days=8)),
        _item(status="mastered", mastered=True, created_at=now),
        _item(status="learning", last_reviewed_at=now - timedelta(hours=30)),
    ]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=items)))
    )

    stats = await repo.count_stats(fake_session, project_id, user_id)

    assert stats["total"] == 4
    assert stats["new_count"] == 1
    assert stats["learning_count"] == 2
    assert stats["mastered_count"] == 1
    assert stats["added_this_week"] == 3
    assert stats["due_for_review"] >= 2


@pytest.mark.asyncio
async def test_normalize_pos_list_titles_updates_mismatch(fake_session):
    project_id = uuid4()
    user_id = uuid4()
    item = _item(part_of_speech="verb", list_title="General")
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[item])))
    )

    changed = await repo.normalize_pos_list_titles(fake_session, user_id, project_id)

    assert changed == 1
    assert item.list_title == "verbs"
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_pos_group_summaries_groups_by_part_of_speech(fake_session):
    items = [
        _item(content="a", part_of_speech="noun", status="new"),
        _item(content="b", part_of_speech="noun", status="mastered", mastered=True),
        _item(content="run", part_of_speech="verb", status="learning"),
    ]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=items)))
    )

    groups = await repo.pos_group_summaries(fake_session, uuid4(), uuid4())

    by_pos = {str(g["part_of_speech"]): g for g in groups}
    assert by_pos["noun"]["count"] == 2
    assert by_pos["noun"]["new_count"] == 1
    assert by_pos["noun"]["mastered_count"] == 1
    assert by_pos["verb"]["learning_count"] == 1


@pytest.mark.asyncio
async def test_deck_summaries_skips_pos_titles(fake_session):
    items = [
        _item(content="hola", list_title="Travel", status="new"),
        _item(content="nouns-only", list_title="nouns", status="new"),
    ]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=items)))
    )

    decks = await repo.deck_summaries(fake_session, uuid4(), uuid4())

    assert len(decks) == 1
    assert decks[0]["title"] == "Travel"
    assert decks[0]["count"] == 1


@pytest.mark.asyncio
async def test_list_by_pos_filters_and_paginates(fake_session):
    # list_by_pos now pushes the POS filter + sort + pagination into SQL, so the
    # repository returns whatever the (filtered, sorted, paginated) query yields.
    # Simulate the DB returning the already-filtered noun page in sorted order.
    noun_items = [
        _item(content="apple", part_of_speech="noun"),
        _item(content="zebra", part_of_speech="noun"),
    ]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = noun_items
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    page = await repo.list_by_pos(fake_session, uuid4(), uuid4(), "noun", limit=1, offset=0)

    # The function issues exactly one filtered query (not the old 5000-row load).
    fake_session.execute.assert_awaited_once()
    assert page == noun_items


def test_pos_variants_covers_singular_and_plural():
    # Filtering in SQL needs to match every stored form that normalizes to the key.
    assert "noun" in repo._pos_variants("noun")
    assert "nouns" in repo._pos_variants("noun")
    assert "verb" in repo._pos_variants("verb")
    assert "verbs" in repo._pos_variants("verb")
    assert "others" in repo._pos_variants("other")
    assert "other" in repo._pos_variants("other")


@pytest.mark.asyncio
async def test_create_sets_pos_list_title(fake_session):
    created = await repo.create(
        fake_session,
        user_id=uuid4(),
        project_id=uuid4(),
        content="  hello  ",
        part_of_speech="Noun",
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    assert created.part_of_speech == "noun"
    assert created.list_title == "nouns"


@pytest.mark.asyncio
async def test_update_syncs_mastered_fields(fake_session):
    item = _item(status="new")
    item.status = "new"
    item.mastered = False
    item.mastered_at = None

    updated = await repo.update(fake_session, item, status="mastered")

    assert updated.status == "mastered"
    assert updated.mastered is True
    assert updated.mastered_at is not None


@pytest.mark.asyncio
async def test_delete_by_id_returns_rowcount(fake_session):
    mock_result = MagicMock()
    mock_result.rowcount = 1
    fake_session.execute.return_value = mock_result

    deleted = await repo.delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is True


@pytest.mark.asyncio
async def test_delete_by_list_empty_title_returns_zero(fake_session):
    deleted = await repo.delete_by_list(fake_session, uuid4(), uuid4(), "   ")

    assert deleted == 0
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_create_deck_item_delegates_to_create(fake_session, monkeypatch):
    user_id = uuid4()
    project_id = uuid4()
    mock_item = _item(list_title="Travel")
    create_mock = AsyncMock(return_value=mock_item)
    monkeypatch.setattr(repo, "create", create_mock)

    result = await repo.create_deck_item(
        fake_session,
        user_id=user_id,
        project_id=project_id,
        deck_title=" Travel ",
        content=" hola ",
        definition="hi",
    )

    create_mock.assert_awaited_once()
    assert result is mock_item
