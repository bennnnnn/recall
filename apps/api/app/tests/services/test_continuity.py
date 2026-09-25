"""Earlier-conversation detection and the unsummarized prompt gap."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.prompt_constants.routing import recalls_earlier_conversation


@pytest.mark.parametrize(
    "text",
    [
        "what did we decide last month",
        "which couch did we pick last year",
        "What did I say about that?",
        "Didn't I mention this before?",
        "What were we talking about yesterday?",
        "Which one did I choose?",
        "Can we continue where we left off?",
        "Pick up from where we left off.",
        "You know the thing I told you about.",
        "What was my idea again?",
    ],
)
def test_recalls_earlier_conversation(text: str):
    assert recalls_earlier_conversation(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "hi",
        "what is 2+2",
        "draw a dog",
        "",
        "How did weather forecasting improve?",
        "How do we pickle onions?",
    ],
)
def test_ordinary_turns_do_not_recall_earlier_conversation(text: str):
    assert recalls_earlier_conversation(text) is False


@pytest.mark.asyncio
async def test_prompt_includes_messages_between_summary_and_recent_window():
    from app.services.chat.prompt_builder import build_prompt_messages

    chat_id = uuid4()
    user = MagicMock(
        id=uuid4(),
        email="test@example.com",
        location_enabled=False,
        response_style="balanced",
        response_tone="casual",
        locale="en",
        timezone="UTC",
        custom_instructions=None,
    )
    user.name = "Test User"
    chat = MagicMock(
        id=chat_id,
        project_id=None,
        summary="We compared couches.",
        summary_message_count=70,
    )
    window = []
    for index in range(20):
        row = MagicMock(role="user", content=f"recent-{index}")
        row.id = uuid4()
        row.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        window.append(row)
    gap_row = MagicMock(role="user", content="the blue couch is the one")
    gap_row.id = uuid4()
    gap_row.created_at = datetime(2025, 12, 1, tzinfo=UTC)

    class _Session:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_args):
            return False

    with (
        patch("app.services.chat.prompt_builder.SessionLocal", _Session),
        patch(
            "app.services.chat.prompt_builder.messages_repo.count_for_chat",
            AsyncMock(return_value=100),
        ),
        patch(
            "app.services.chat.prompt_builder.messages_repo.list_before",
            AsyncMock(return_value=[gap_row]),
        ) as list_before,
        patch("app.modules.memory.get_memory_block", AsyncMock(return_value="")),
        patch("app.modules.todos.build_todos_system_section", AsyncMock(return_value=None)),
        patch(
            "app.modules.learning.load_learning_classes_for_prompt",
            AsyncMock(return_value=""),
        ),
    ):
        messages = await build_prompt_messages(
            user,
            chat_id,
            Settings(attachment_rag_enabled=False, chat_history_rag_enabled=False),
            query_text="hi",
            chat=chat,
            summary=chat.summary,
            rich_context=True,
            recent_messages=window,
        )

    list_before.assert_awaited_once()
    contents = [message["content"] for message in messages]
    assert "the blue couch is the one" in contents
    assert contents.index("the blue couch is the one") < contents.index("recent-0")


@pytest.mark.asyncio
async def test_prompt_keeps_the_message_pushed_out_by_the_current_turn():
    from app.services.chat.prompt_builder import build_prompt_messages

    chat_id = uuid4()
    user = MagicMock(
        id=uuid4(),
        email="test@example.com",
        location_enabled=False,
        response_style="balanced",
        response_tone="casual",
        locale="en",
        timezone="UTC",
        custom_instructions=None,
    )
    user.name = "Test User"
    chat = MagicMock(id=chat_id, project_id=None, summary=None, summary_message_count=0)
    current_id = uuid4()
    window = []
    for index in range(20):
        row = MagicMock(role="user", content=f"stored-{index}")
        row.id = uuid4()
        row.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        window.append(row)
    current = MagicMock(role="user", content="what did I say about that?")
    current.id = current_id
    current.created_at = datetime(2026, 1, 2, tzinfo=UTC)

    class _Session:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_args):
            return False

    with (
        patch("app.services.chat.prompt_builder.SessionLocal", _Session),
        patch(
            "app.services.chat.prompt_builder.messages_repo.count_for_chat",
            AsyncMock(return_value=20),
        ),
        patch(
            "app.services.chat.prompt_builder.messages_repo.list_before",
            AsyncMock(return_value=[]),
        ),
        patch("app.modules.memory.get_memory_block", AsyncMock(return_value="")),
        patch("app.modules.todos.build_todos_system_section", AsyncMock(return_value=None)),
        patch(
            "app.modules.learning.load_learning_classes_for_prompt",
            AsyncMock(return_value=""),
        ),
    ):
        messages = await build_prompt_messages(
            user,
            chat_id,
            Settings(
                attachment_rag_enabled=False,
                chat_history_rag_enabled=False,
                recent_message_window=20,
            ),
            query_text=current.content,
            chat=chat,
            rich_context=True,
            recent_messages=[*window, current],
            current_user_message_id=current_id,
        )

    contents = [message["content"] for message in messages]
    assert "stored-0" in contents
    assert contents.index("stored-0") < contents.index("stored-1")
