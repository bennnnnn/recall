from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.prompt_builder import build_prompt_messages


@pytest.mark.asyncio
async def test_build_prompt_includes_web_search_hint():
    user = MagicMock()
    user.response_style = "balanced"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"
    user.location = None
    user.response_tone = "funny"

    with (
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(user, uuid4(), Settings())

    assert "Web search results" in messages[0]["content"]
