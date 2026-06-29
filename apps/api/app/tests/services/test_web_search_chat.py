from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat import build_prompt_messages


@pytest.mark.asyncio
async def test_build_prompt_includes_web_search_hint():
    user = MagicMock()
    user.response_style = "balanced"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"
    user.location = None
    user.response_tone = "funny"

    session = AsyncMock()

    with (
        patch(
            "app.services.chat.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.todos_service.load_todos_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.chats_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(session, user, uuid4(), Settings())

    assert "Web search results" in messages[0]["content"]
