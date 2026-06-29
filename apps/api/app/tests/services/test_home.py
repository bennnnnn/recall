from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import ProjectStats
from app.services import home as home_service


def _user(**kwargs):
    u = MagicMock()
    u.id = kwargs.get("id", uuid4())
    u.name = kwargs.get("name", "Alex")
    u.timezone = kwargs.get("timezone", "UTC")
    u.memory_enabled = kwargs.get("memory_enabled", True)
    return u


def _todo(content: str, *, minutes_from_now: int, topic: str = "Work"):
    item = MagicMock()
    item.id = uuid4()
    item.content = content
    item.topic = topic
    due = datetime.now(UTC) + timedelta(minutes=minutes_from_now)
    item.due_at = due
    item.checked = False
    return item


def _project(title: str = "Learning English", *, total: int = 5):
    project = MagicMock()
    project.id = uuid4()
    project.title = title
    project.description = None
    project.kind = "language"
    project.level = "level2"
    return project


@contextmanager
def _home_patches(**overrides):
    defaults = {
        "list_due_soon": [],
        "list_for_user_chats": [],
        "list_active_suggestions": [],
        "load_relevant_memories": [],
        "list_projects": [],
        "count_project_stats": {
            "total": 0,
            "new_count": 0,
            "learning_count": 0,
            "mastered_count": 0,
            "added_this_week": 0,
            "due_for_review": 0,
        },
    }
    defaults.update(overrides)
    with (
        patch.object(
            home_service.todos_repo,
            "list_due_soon",
            AsyncMock(return_value=defaults["list_due_soon"]),
        ),
        patch.object(
            home_service.chats_repo,
            "list_for_user",
            AsyncMock(return_value=defaults["list_for_user_chats"]),
        ),
        patch.object(
            home_service.suggestions_repo,
            "list_active",
            AsyncMock(return_value=defaults["list_active_suggestions"]),
        ),
        patch.object(
            home_service.memory_service,
            "load_relevant_memories",
            AsyncMock(return_value=defaults["load_relevant_memories"]),
        ),
        patch.object(
            home_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=defaults["list_projects"]),
        ),
        patch.object(
            home_service.project_items_repo,
            "count_stats",
            AsyncMock(return_value=defaults["count_project_stats"]),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_build_home_includes_urgent_todo():
    session = AsyncMock()
    user = _user()
    urgent = _todo("Pay rent", minutes_from_now=30)

    with _home_patches(list_due_soon=[urgent]):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert len(screen.urgent_todos) == 1
    assert screen.urgent_todos[0].content == "Pay rent"
    assert "Pay rent" in (screen.subtitle or "")
    assert not any(s.kind == "todo" for s in screen.starters)


@pytest.mark.asyncio
async def test_build_home_greeting_uses_name():
    session = AsyncMock()
    user = _user(name="Sam")

    with _home_patches():
        screen = await home_service.build_home_screen(session, user, Settings())

    assert "Sam" in screen.greeting
    assert len(screen.starters) >= 2


@pytest.mark.asyncio
async def test_build_home_language_project_starters():
    session = AsyncMock()
    user = _user()
    project = _project()

    with _home_patches(
        list_projects=[project],
        count_project_stats={
            "total": 3,
            "new_count": 2,
            "learning_count": 1,
            "mastered_count": 0,
            "added_this_week": 0,
            "due_for_review": 2,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    kinds = {s.kind for s in screen.starters}
    assert screen.project_highlight is not None
    assert screen.project_highlight.title == "Learning English"
    assert "project" not in kinds
    assert "chat" not in kinds
    assert "memory" not in kinds
    assert screen.subtitle is None


@pytest.mark.asyncio
async def test_build_home_highlight_skips_duplicate_starters():
    session = AsyncMock()
    user = _user()
    project = _project()
    chat = MagicMock()
    chat.title = "English vocabulary practice"
    memory = MagicMock()
    memory.type = "project"
    memory.text = "User is actively engaged in vocabulary expansion"

    with _home_patches(
        list_projects=[project],
        list_for_user_chats=[chat],
        load_relevant_memories=[memory],
        count_project_stats={
            "total": 10,
            "new_count": 3,
            "learning_count": 4,
            "mastered_count": 3,
            "added_this_week": 1,
            "due_for_review": 7,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is not None
    starter_texts = {s.text for s in screen.starters}
    assert "Pick up where we left off" not in starter_texts
    assert "Keep building" not in starter_texts
    assert "Practice English" not in starter_texts


def test_time_starters_vary_by_hour():
    user = _user()
    with patch.object(home_service, "_local_hour", return_value=8):
        morning = home_service._time_starters(user)
    with patch.object(home_service, "_local_hour", return_value=19):
        evening = home_service._time_starters(user)
    assert morning[0].text != evening[0].text


def test_memory_starter_skips_profile_name_facts():
    memory = MagicMock()
    memory.type = "profile"
    memory.text = "User's name is Binalfew"
    assert home_service._memory_starter(memory) is None


def test_memory_starter_english_learning_uses_specific_label():
    memory = MagicMock()
    memory.type = "focus"
    memory.text = "User is learning English"
    starter = home_service._memory_starter(memory)
    assert starter is not None
    assert starter.text == "Practice English"
    assert "English learning" in starter.prompt


def test_memory_starter_profile_english_learning():
    memory = MagicMock()
    memory.type = "profile"
    memory.text = "User is learning English vocabulary"
    starter = home_service._memory_starter(memory)
    assert starter is not None
    assert starter.text == "Practice English"


def test_chat_starter_uses_friendly_label():
    starter = home_service._chat_starter(["Binalfew Software Engineer Context"])
    assert starter is not None
    assert starter.text == "Pick up where we left off"
    assert "Software Engineer" in starter.prompt


def test_urgent_subtitle_single_uses_time_not_topic():
    user = _user(timezone="UTC")
    due = datetime.now(UTC) + timedelta(minutes=30)
    urgent = [
        home_service.HomeUrgentTodo(
            id=uuid4(),
            content="Walk",
            topic="Walk",
            due_at=due,
            minutes_until=30,
        )
    ]
    subtitle = home_service._urgent_subtitle(user, urgent)
    assert subtitle is not None
    assert "Walk" in subtitle
    assert "(Walk)" not in subtitle
    assert "today at" in subtitle or "Coming up" in subtitle


def test_urgent_subtitle_multiple_counts():
    user = _user()
    due = datetime.now(UTC) + timedelta(minutes=10)
    urgent = [
        home_service.HomeUrgentTodo(
            id=uuid4(),
            content="A",
            topic="General",
            due_at=due,
            minutes_until=10,
        ),
        home_service.HomeUrgentTodo(
            id=uuid4(),
            content="B",
            topic="General",
            due_at=due,
            minutes_until=10,
        ),
    ]
    assert home_service._urgent_subtitle(user, urgent) == "2 reminders in the next hour."


def test_looks_internal_filters_user_facts():
    assert home_service._looks_internal("User's name is Binalfew")
    assert not home_service._looks_internal("Building the Recall app")


def test_looks_internal_allows_learning_facts():
    assert not home_service._looks_internal("User is learning English")


def test_project_starters_empty_language_project():
    project = _project()
    stats = ProjectStats()
    starters = home_service._project_starters(project, stats)
    assert starters == []
