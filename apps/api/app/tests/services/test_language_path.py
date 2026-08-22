from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.projects.crud import group_items
from app.services.projects.path import (
    append_chapter,
    build_path_progress,
    chapter_is_complete,
    enqueue_language_path_job,
    normalize_path_titles,
    parse_learning_path,
    resolve_add_list_title,
    sort_list_titles,
    up_next_chapter,
)
from app.services.projects.path_seed import seed_language_path
from app.services.projects.prompt_context import format_projects_block


def _project(**kw: object) -> MagicMock:
    project = MagicMock()
    project.id = kw.get("id", uuid4())
    project.user_id = kw.get("user_id", uuid4())
    project.title = kw.get("title", "Spanish")
    project.kind = "language"
    project.level = kw.get("level", "level1")
    project.target_language = kw.get("target_language", "es")
    project.native_language = kw.get("native_language", "en")
    project.daily_goal = kw.get("daily_goal", 5)
    project.learning_path = kw.get("learning_path", ["Greetings", "Food"])
    return project


def _item(content: str, list_title: str, *, mastered: bool = False) -> MagicMock:
    item = MagicMock()
    item.id = uuid4()
    item.project_id = None
    item.list_title = list_title
    item.content = content
    item.status = "mastered" if mastered else "new"
    item.mastered = mastered
    item.definition = f"def {content}"
    item.example_sentence = None
    item.note = None
    item.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    item.mastered_at = None
    item.last_reviewed_at = None
    item.last_incorrect_at = None
    item.review_count = 0
    item.ease_factor = 2.5
    item.interval_days = 0
    item.due_at = None
    item.pronunciation_url = None
    return item


def test_normalize_path_titles_drops_general_and_dupes():
    assert normalize_path_titles(["Greetings", " general ", "Greetings", "Food", 12]) == [
        "Greetings",
        "Food",
    ]


def test_normalize_path_titles_keeps_long_catalog_paths():
    titles = [f"Chapter {index}" for index in range(20)]
    assert normalize_path_titles(titles) == titles


def test_parse_learning_path_ignores_non_lists():
    assert parse_learning_path(SimpleNamespace(learning_path=None)) == []
    assert parse_learning_path(MagicMock()) == []


def test_chapter_complete_needs_floor_and_ratio():
    assert not chapter_is_complete(mastered=4, total=4, daily_goal=10)
    assert chapter_is_complete(mastered=4, total=5, daily_goal=10)
    assert not chapter_is_complete(mastered=3, total=5, daily_goal=10)
    assert chapter_is_complete(mastered=3, total=3, daily_goal=3)


def test_up_next_is_first_incomplete_chapter():
    project = _project()
    items = [
        _item("hola", "Greetings", mastered=True),
        _item("adiós", "Greetings", mastered=True),
        _item("gracias", "Greetings", mastered=True),
        _item("por favor", "Greetings", mastered=True),
        _item("buenos días", "Greetings", mastered=True),
        _item("pan", "Food"),
    ]
    progress = build_path_progress(project, items)
    assert progress[0].complete is True
    assert progress[1].complete is False
    assert progress[0].domain
    assert up_next_chapter(project, items) == "Food"


def test_resolve_add_list_title_uses_up_next_when_general():
    project = _project()
    items = [_item("hola", "Greetings")]
    assert resolve_add_list_title(project, "General", items) == "Greetings"
    assert resolve_add_list_title(project, "Travel", items) == "Travel"


def test_append_chapter_skips_general_and_dupes():
    project = _project(learning_path=["Greetings"])
    assert append_chapter(project, "General") is False
    assert append_chapter(project, "Greetings") is False
    assert append_chapter(project, "Travel") is True
    assert project.learning_path == ["Greetings", "Travel"]


def test_group_items_follows_learning_path_order():
    project_id = uuid4()
    zebra = _item("z", "Zebra")
    zebra.project_id = project_id
    apple = _item("a", "Apple")
    apple.project_id = project_id
    groups = group_items([zebra, apple], learning_path=["Zebra", "Apple"])
    assert [group.list_title for group in groups] == ["Zebra", "Apple"]


def test_sort_list_titles_puts_unknown_decks_last():
    assert sort_list_titles(["Travel", "Food", "Greetings"], ["Greetings", "Food"]) == [
        "Greetings",
        "Food",
        "Travel",
    ]


def test_format_projects_block_includes_path():
    project = _project()
    item = _item("hola", "Greetings")
    item.project_id = project.id
    block = format_projects_block([project], [item])
    assert "Learning path" in block
    assert "Teach only words listed under: Greetings" in block


@pytest.mark.asyncio
async def test_enqueue_language_path_job_swallows_redis_errors():
    with patch(
        "app.core.redis.get_redis_client",
        side_effect=RuntimeError("no redis"),
    ):
        await enqueue_language_path_job(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_seed_language_path_copies_catalog_words():
    from app.content.vocab_catalog import catalog_path_titles, catalog_word_count

    user_id = uuid4()
    project_id = uuid4()
    project = _project(id=project_id, user_id=user_id, learning_path=None)
    session = AsyncMock()
    session.commit = AsyncMock()

    class _CM:
        async def __aenter__(self) -> AsyncMock:
            return session

        async def __aexit__(self, *args: object) -> None:
            return None

    created = AsyncMock()
    with (
        patch("app.core.db.SessionLocal", return_value=_CM()),
        patch("app.repositories.projects.get_by_id", AsyncMock(return_value=project)),
        patch("app.repositories.project_items.list_for_user", AsyncMock(return_value=[])),
        patch("app.services.projects.items.create_item", created),
        patch("app.services.projects.common._invalidate_home_for_user", AsyncMock()),
    ):
        await seed_language_path(MagicMock(), user_id=user_id, project_id=project_id)

    assert project.learning_path == catalog_path_titles("es", level=1)
    assert created.await_count == catalog_word_count("es", level=1)
    assert created.await_count > 0


def test_needs_catalog_sync_when_path_is_old_llm_titles():
    from app.content.vocab_catalog import catalog_path_titles, decks_for_language
    from app.services.learning.path_seed import needs_catalog_sync

    project = _project(learning_path=["Greetings and Introductions", "Everyday Objects"])
    assert needs_catalog_sync(project, [_item("hola", "Greetings and Introductions")]) is True

    project = _project(learning_path=catalog_path_titles("es", level=1))

    items = [
        _item(word.content, deck.title)
        for deck in decks_for_language("es", level=1)
        for word in deck.words
    ]
    assert needs_catalog_sync(project, items) is False


def test_needs_catalog_sync_when_word_sits_on_old_list_title():
    from app.content.vocab_catalog import catalog_path_titles, decks_for_language
    from app.services.learning.path_seed import needs_catalog_sync

    first = decks_for_language("es", level=1)[0]
    word = first.words[0]
    project = _project(learning_path=catalog_path_titles("es", level=1))
    leftover = [_item(word.content, "Family")]
    leftover.extend(
        _item(other.content, deck.title)
        for deck in decks_for_language("es", level=1)
        for other in deck.words
        if not (deck.title == first.title and other.content == word.content)
    )
    assert needs_catalog_sync(project, leftover) is True
