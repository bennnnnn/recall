from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat import (
    build_prompt_messages,
    estimate_tokens,
    format_user_name_only_block,
    format_user_profile_block,
    is_broad_self_question,
    is_lightweight_chat_turn,
    is_writing_deliverable_request,
    max_output_tokens_for_style,
)


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def _offline_session_patches():
    return (
        patch("app.services.chat.stream.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.turn_prep.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.post_turn.SessionLocal", _FakeSessionCM),
        patch("app.services.chat.SessionLocal", _FakeSessionCM),
    )


def _quiz_message_repo_patches():
    """New quiz helpers hit the DB; unit tests must stub them off AsyncMock sessions."""
    return (
        patch(
            "app.services.chat.messages_repo.get_last_quiz_assistant",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.messages_repo.count_quiz_letter_answers_since",
            AsyncMock(return_value=0),
        ),
    )


@pytest.fixture
def stream_offline_io():
    """Keep stream_chat_response unit tests off DB/Redis after turn_prep pre-sync."""
    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        stack.enter_context(patch("app.services.chat.post_turn.seed_usage_from_db", AsyncMock()))
        stack.enter_context(patch("app.services.chat.quota_service.refund_usage", AsyncMock()))
        stack.enter_context(
            patch("app.services.chat.messages_repo.list_recent", AsyncMock(return_value=[]))
        )
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch(
                "app.services.chat.web_search_service.is_vocab_quiz_answer",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.calendar_service.has_write_access",
                AsyncMock(return_value=False),
            )
        )
        yield


def test_estimate_tokens_minimum():
    assert estimate_tokens("") == 1
    assert estimate_tokens("hello") == 1


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Send me an email to my wife", True),
        ("email my boss about PTO", True),
        ("what is Python", False),
    ],
)
def test_is_writing_deliverable_request(text: str, expected: bool):
    assert is_writing_deliverable_request(text) is expected


@pytest.mark.asyncio
async def test_build_prompt_includes_email_draft_hint_for_email_request():
    user = MagicMock()
    user.id = uuid4()
    user.name = "Test User"
    user.email = "test@example.com"
    user.location = None
    user.response_style = "balanced"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None

    session = AsyncMock()

    with (
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.messages_repo.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(
            session,
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text="Send an email to my wife",
        )

    system = messages[0]["content"]
    assert "Email and message drafting" in system
    assert "draft immediately" in system.lower()


@pytest.mark.asyncio
async def test_build_prompt_injects_custom_instructions():
    user = MagicMock()
    user.name = "Test User"
    user.email = "test@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None
    user.custom_instructions = "Always answer in bullet points and cite sources."

    session = AsyncMock()

    with (
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.messages_repo.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(session, user, uuid4(), Settings())

    system = messages[0]["content"]
    assert "User's personal instructions:" in system
    assert "Always answer in bullet points and cite sources." in system


@pytest.mark.asyncio
async def test_build_prompt_reuses_passed_chat_without_db_fetch():
    user = MagicMock()
    user.name = "Test User"
    user.email = "test@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = None
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None
    user.custom_instructions = None

    passed_chat = MagicMock()
    passed_chat.project_id = None
    passed_chat.summary = None
    passed_chat.summary_message_count = 0

    session = AsyncMock()
    get_by_id = AsyncMock()

    with (
        patch("app.services.chat.chats_repo.get_by_id", get_by_id),
        patch(
            "app.services.chat.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.messages_repo.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        await build_prompt_messages(
            session,
            user,
            uuid4(),
            Settings(),
            chat=passed_chat,
        )

    get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_prompt_omits_custom_instructions_block_when_empty():
    user = MagicMock()
    user.name = "Test User"
    user.email = "test@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None
    user.custom_instructions = None

    session = AsyncMock()

    with (
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.messages_repo.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(session, user, uuid4(), Settings())

    system = messages[0]["content"]
    assert "User's personal instructions:" not in system


@pytest.mark.asyncio
async def test_build_prompt_includes_memory_and_style():
    user = MagicMock()
    user.name = "Biniyam Mecuriaw"
    user.email = "bmecuriaw@gmail.com"
    user.location = None
    user.response_style = "short"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"
    user.response_tone = "funny"

    session = AsyncMock()

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[AsyncMock(type="preference", text="likes Python")]),
        ),
        patch(
            "app.services.chat.messages_repo.list_recent",
            return_value=[AsyncMock(role="user", content="Hi")],
        ),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value="Known facts:\n- [preference] likes Python",
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=None),
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

    assert messages[0]["role"] == "system"
    assert "Biniyam Mecuriaw" in messages[0]["content"]
    assert "bmecuriaw@gmail.com" in messages[0]["content"]
    assert "short" in messages[0]["content"].lower()
    assert "1-3 sentences" in messages[0]["content"].lower()
    assert "**HTML UI**" not in messages[0]["content"]
    assert "Python" in messages[0]["content"]
    assert "clarifying questions" in messages[0]["content"].lower()
    assert messages[-1] == {"role": "user", "content": "Hi"}


@pytest.mark.asyncio
async def test_build_prompt_recalled_count_counts_section_headers():
    """`recalled` must reflect `## {Label}` headers emitted by format_memory_block,
    not "- " bullets (which it never produces). Regression for the chip-always-0 bug."""
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"

    session = AsyncMock()
    out: dict[str, object] = {}

    # Real format: one `## {Label}` header per injected section.
    block = (
        "Known facts about the user:\n\n## Profile\nLives in Addis\n\n## Preferences\nlikes Python"
    )

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[AsyncMock(type="profile", text="Lives in Addis")]),
        ),
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value=block,
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=None),
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
        await build_prompt_messages(session, user, uuid4(), Settings(), out=out)

    assert out["recalled"] == 2
    assert out["memory_hints"] == ["Profile", "Preferences"]


@pytest.mark.asyncio
async def test_build_prompt_recalled_count_zero_when_no_memory():
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"

    session = AsyncMock()
    out: dict[str, object] = {}

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value="",
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=None),
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
        await build_prompt_messages(session, user, uuid4(), Settings(), out=out)

    assert out["recalled"] == 0
    assert out["memory_hints"] == []


@pytest.mark.asyncio
async def test_build_prompt_includes_response_tone():
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "professional"
    user.memory_enabled = False
    user.locale = "en"
    user.timezone = "UTC"

    session = AsyncMock()

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value="",
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=None),
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

    assert "Tone: PROFESSIONAL" in messages[0]["content"]
    assert "Privacy:" in messages[0]["content"]
    assert "'Who am I?'" in messages[0]["content"]
    assert "do NOT list email" in messages[0]["content"]


@pytest.mark.asyncio
async def test_build_prompt_includes_locale_hint_for_amharic():
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "casual"
    user.memory_enabled = False
    user.locale = "am"
    user.timezone = "UTC"

    session = AsyncMock()

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value="",
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=None),
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

    system = messages[0]["content"]
    assert "Amharic" in system
    assert "locale code: am" in system
    assert "switch languages" in system.lower() or "switch language" in system.lower()


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Who am I", True),
        ("who am i?", True),
        ("Tell me about me", True),
        ("Where am I?", False),
        ("What's my email?", False),
        ("What's my name?", False),
    ],
)
def test_is_broad_self_question(text, expected):
    assert is_broad_self_question(text) is expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hi", True),
        ("Thanks!", True),
        ("ok", True),
        ("Hello there", False),
        ("What's on my calendar today?", False),
        ("add eggs to groceries", False),
    ],
)
def test_is_lightweight_chat_turn(text, expected):
    assert is_lightweight_chat_turn(text) is expected


def test_is_lightweight_skipped_during_vocab_answer():
    assert is_lightweight_chat_turn("k", active_vocab_turn=True) is False
    assert is_lightweight_chat_turn("ok", active_vocab_turn=True) is False


@pytest.mark.asyncio
async def test_build_prompt_minimal_for_who_am_i():
    user = MagicMock()
    user.name = "Binalfew Mecuriaw"
    user.email = "secret@example.com"
    user.location = "San Francisco, CA"
    user.location_enabled = True
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"

    session = AsyncMock()

    with patch("app.services.chat.messages_repo.list_recent", return_value=[]):
        messages = await build_prompt_messages(
            session,
            user,
            AsyncMock(),
            Settings(),
            minimal_personal_context=True,
        )

    system = messages[0]["content"]
    assert "Binalfew" in system
    assert "secret@example.com" not in system
    assert "San Francisco" not in system
    assert "general 'who am I' question" in system
    assert "Recall has two todo features" not in system


@pytest.mark.asyncio
async def test_build_prompt_day_planning_injects_daily_learning():
    user = MagicMock()
    user.id = uuid4()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.location_enabled = False
    user.response_style = "balanced"
    user.response_tone = "casual"
    user.memory_enabled = False
    user.locale = "en"
    user.timezone = "America/Los_Angeles"
    user.custom_instructions = None

    session = AsyncMock()
    learning_block = (
        "Today's learning progress (local calendar day, authoritative):\n"
        "- English · Beginner (vocabulary quiz): 0/5 words mastered today "
        "(not started — 5 left for today's vocabulary quiz)"
    )

    with (
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.memory_service.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.projects_service.load_daily_learning_summary_for_prompt",
            AsyncMock(return_value=learning_block),
        ) as daily_mock,
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value="SHOULD NOT USE"),
        ),
        patch(
            "app.services.chat.chats_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(
            session,
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text="What's still open for me to finish tonight?",
            client_timezone="America/Los_Angeles",
        )

    daily_mock.assert_awaited_once()
    system = messages[0]["content"]
    assert learning_block in system
    assert "vocabulary quiz" in system
    assert "Never reuse yesterday's scores from memory" in system
    assert "SHOULD NOT USE" not in system


@pytest.mark.asyncio
async def test_build_prompt_minimal_for_vocab_quiz_answer():
    user = MagicMock()
    user.name = "Binalfew Mecuriaw"
    user.email = "secret@example.com"
    user.location = "San Francisco, CA"
    user.location_enabled = True
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"

    session = AsyncMock()

    with (
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.chats_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(
            session,
            user,
            uuid4(),
            Settings(),
            minimal_quiz_context=True,
        )

    system = messages[0]["content"]
    assert "Vocabulary (English words)" in system
    assert "vocab_quiz" in system
    assert "Recall has two todo features" not in system
    assert "Web search results" not in system
    assert "Google Calendar" not in system
    assert "Known facts about the user" not in system


@pytest.mark.asyncio
async def test_build_prompt_minimal_quiz_includes_project_context():
    from uuid import uuid4

    user = MagicMock()
    user.id = uuid4()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = False
    user.locale = "en"
    user.timezone = "UTC"

    chat_id = uuid4()
    project_id = uuid4()
    chat = MagicMock()
    chat.project_id = project_id
    session = AsyncMock()

    with (
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.chats_repo.get_by_id",
            AsyncMock(return_value=chat),
        ),
        patch(
            "app.services.chat.projects_service.load_project_quiz_context",
            AsyncMock(return_value="Active vocabulary quiz — project: English"),
        ) as quiz_ctx_mock,
    ):
        messages = await build_prompt_messages(
            session,
            user,
            chat_id,
            Settings(),
            minimal_quiz_context=True,
        )

    quiz_ctx_mock.assert_awaited_once()
    assert "Active vocabulary quiz" in messages[0]["content"]


@pytest.mark.asyncio
async def test_should_minimal_quiz_context_after_vocab_quiz_fence():
    from app.services.chat.turn_prep import _should_minimal_quiz_context

    chat_id = uuid4()
    session = AsyncMock()
    quiz_msg = MagicMock()
    quiz_msg.content = (
        '```vocab_quiz\n{"quiz_type":"trivia","word":"History","question":"Which wonder?",'
        '"correct":"A","choices":[{"letter":"A","text":"Colossus"},'
        '{"letter":"B","text":"Pyramid"}]}\n```'
    )

    with patch(
        "app.services.chat.messages_repo.get_last_quiz_assistant",
        AsyncMock(return_value=quiz_msg),
    ):
        assert await _should_minimal_quiz_context(session, chat_id, "B") is True
        assert await _should_minimal_quiz_context(session, chat_id, "more please") is False


@pytest.mark.asyncio
async def test_should_minimal_quiz_context_false_without_prior_quiz():
    from app.services.chat.turn_prep import _should_minimal_quiz_context

    chat_id = uuid4()
    session = AsyncMock()

    with patch(
        "app.services.chat.messages_repo.get_last_quiz_assistant",
        AsyncMock(return_value=None),
    ):
        assert await _should_minimal_quiz_context(session, chat_id, "A") is False


@pytest.mark.asyncio
async def test_build_prompt_passes_client_timezone():
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = False
    user.locale = "en"
    user.timezone = "UTC"

    session = AsyncMock()
    load_todos = AsyncMock(return_value=None)

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.services.chat.messages_repo.list_recent", return_value=[]),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value="",
        ),
        patch(
            "app.services.chat.todos_service.build_todos_system_section",
            load_todos,
        ),
        patch(
            "app.services.chat.projects_service.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.chat.chats_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.time_context_service.format_time_context",
            return_value="LOCAL_TIME_BLOCK",
        ) as format_time,
    ):
        await build_prompt_messages(
            session,
            user,
            uuid4(),
            Settings(),
            client_timezone="America/New_York",
        )

    load_todos.assert_awaited_once()
    assert load_todos.await_args.kwargs["client_timezone"] == "America/New_York"
    format_time.assert_called_once_with("America/New_York", "en", None)


def test_is_vocab_quiz_answer():
    from app.services.web_search import is_vocab_quiz_answer

    assert is_vocab_quiz_answer("B") is True
    assert is_vocab_quiz_answer("c.") is True
    assert is_vocab_quiz_answer("Is it a?") is True
    assert is_vocab_quiz_answer("hello") is False


def test_max_output_tokens_for_style():
    settings = Settings(max_output_tokens=1200)
    assert max_output_tokens_for_style("short", settings) == 400
    assert max_output_tokens_for_style("balanced", settings) == 1200
    assert max_output_tokens_for_style("detailed", settings) == 2200
    settings = Settings(max_output_tokens=1200)
    assert max_output_tokens_for_style("short", settings) == 400
    assert max_output_tokens_for_style("balanced", settings) == 1200
    assert max_output_tokens_for_style("detailed", settings) == 2200


@pytest.mark.asyncio
async def test_stream_does_not_duplicate_user_message(stream_offline_io):
    from app.services import chat as chat_module

    tokens = ["Hello", " there"]

    async def fake_stream(**kwargs):
        for t in tokens:
            yield t

    user_id = AsyncMock()
    chat_id = AsyncMock()

    mock_build = AsyncMock(
        return_value=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "question"},
        ]
    )

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=1)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch("app.services.chat.build_prompt_messages", mock_build),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        collected = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=user_id,
            chat_id=chat_id,
            content="question",
        ):
            collected.append(tok)

    assert collected == tokens
    assert mock_build.await_count == 1


@pytest.mark.asyncio
async def test_memory_extraction_runs_on_later_turn(stream_offline_io):
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, memory_extract_every_n_turns=1),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="second turn info",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    # Memory is enqueued every turn when memory_extract_every_n_turns=1.
    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert job_types.count("memory") == 1
    assert "topic" not in job_types
    assert "todos" not in job_types
    assert "projects" not in job_types


@pytest.mark.asyncio
async def test_memory_extraction_skipped_when_memory_disabled(stream_offline_io):
    """When the user has memory_enabled=False, the memory job must not be
    enqueued at all — previously it was enqueued every N turns and the
    extraction worker no-op'd internally, wasting a stream-job cycle."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.memory_enabled = False

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, memory_extract_every_n_turns=1),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="second turn info",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert "memory" not in job_types


@pytest.mark.asyncio
async def test_memory_extraction_skipped_between_batch_turns(stream_offline_io):
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=2)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100, memory_extract_every_n_turns=3),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="turn two chit chat",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert "memory" not in job_types


@pytest.mark.asyncio
async def test_stream_skips_pre_reply_todo_llm_sync(stream_offline_io):
    """Todo LLM extraction must not block the chat path before streaming."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "ok"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=1)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.todos_service.should_pre_sync_todos",
            MagicMock(return_value=True),
        ),
        patch(
            "app.services.chat.todos_service.sync_todos_before_reply",
            AsyncMock(),
        ) as pre_sync,
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
    ):
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="add eggs to groceries",
        ):
            pass

    pre_sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_turn_jobs_enqueue_todos_when_transcript_matches(stream_offline_io):
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "Added eggs to your grocery list."

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        result: dict[str, str] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="add eggs to groceries",
            result=result,
        ):
            pass
        finalize = result.get("_finalize_task")
        if finalize is not None:
            await finalize

    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert "todos" in job_types
    assert result.get("todos_sync") == "1"


@pytest.mark.asyncio
async def test_stream_sets_final_content_on_cancel(stream_offline_io):
    """On a user-initiated stop, the server persists text the client may not have
    rendered yet; `result["final_content"]` carries the authoritative persisted
    text so the client can reconcile (stop/regenerate desync fix)."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        for w in ["one ", "two ", "three "]:
            yield w

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    cancel_after = {"n": 0}

    def should_cancel():
        cancel_after["n"] += 1
        return cancel_after["n"] > 1  # let the first token through, then cancel

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        result: dict[str, object] = {}
        yielded: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            should_cancel=should_cancel,
            result=result,
        ):
            yielded.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    # Only the first token was yielded before cancel broke the loop.
    assert yielded == ["one "]
    # The authoritative persisted text is exposed for client reconciliation.
    assert result.get("final_content") == "one"


@pytest.mark.asyncio
async def test_cancelled_stream_skips_model_health_sample(stream_offline_io):
    """User stop must not record a failed health sample (poisons fallback routing)."""
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    async def fake_stream(**_kwargs):
        yield "one "
        yield "two "

    record = AsyncMock()
    cancel_after = {"n": 0}

    def should_cancel() -> bool:
        cancel_after["n"] += 1
        return cancel_after["n"] > 1

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=100,
        max_output_tokens=50,
        skip_memory_jobs=True,
    )

    result: dict[str, object] = {}
    with ExitStack() as stack:
        stack.enter_context(
            patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.model_health.record_sample", record))
        stack.enter_context(patch("app.services.chat.stream.finalize_stream_turn_db", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.chat.calendar_service.materialize_calendar_proposals",
                AsyncMock(side_effect=lambda *_a, **_k: _a[-1]),
            )
        )
        stack.enter_context(
            patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=None))
        )
        async for _ in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
            ctx,
            should_cancel=should_cancel,
            result=result,
        ):
            pass
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    record.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_closes_llm_stream_on_cancel(stream_offline_io):
    """Stop generation must aclose the provider stream so upstream tokens stop accruing."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    class TrackedStream:
        def __init__(self) -> None:
            self.aclose_called = False

        def __call__(self, **_kwargs):
            return self

        def __aiter__(self):
            self._remaining = ["one ", "two ", "three "]
            return self

        async def __anext__(self):
            if not self._remaining:
                raise StopAsyncIteration
            return self._remaining.pop(0)

        async def aclose(self) -> None:
            self.aclose_called = True

    tracked = TrackedStream()
    cancel_after = {"n": 0}

    def should_cancel():
        cancel_after["n"] += 1
        return cancel_after["n"] > 1

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", tracked),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            should_cancel=should_cancel,
        ):
            pass

    assert tracked.aclose_called is True


@pytest.mark.asyncio
async def test_stream_places_query_without_location_prompts_to_enable(stream_offline_io):
    """A 'near me' places query with no user.location should yield a deterministic
    'enable location' instant reply and skip web search (no guessing)."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.location = ""  # no location set
    fake_user.location_enabled = False

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    augment = AsyncMock(return_value=([{"role": "system", "content": "sys"}], []))

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=0)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch("app.services.chat.web_search_service.augment_prompt_messages", augment),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", AsyncMock()),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        yielded: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="best restaurants near me",
        ):
            yielded.append(tok)

    # The instant reply is the enable-location prompt.
    assert any("Settings" in t and "location" in t.lower() for t in yielded), yielded
    # Web search must be skipped (no guessing "near me").
    augment.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_places_query_uses_client_location_without_profile(stream_offline_io):
    """Ephemeral client GPS should run web search instead of the enable-location block."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.location = ""
    fake_user.location_enabled = False

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    augment = AsyncMock(return_value=([{"role": "system", "content": "sys"}], []))

    async def fake_stream(**kwargs):
        yield "answer"

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.users_repo.update", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=0)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch("app.services.chat.web_search_service.augment_prompt_messages", augment),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        yielded: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="best restaurants near me",
            client_location="San Francisco, CA",
        ):
            yielded.append(tok)

    assert not any("Settings" in t for t in yielded), yielded
    augment.assert_awaited_once()
    assert augment.await_args.kwargs["user_location"] == "San Francisco, CA"


@pytest.mark.asyncio
async def test_stream_persists_raw_text_when_enrichment_fails(stream_offline_io):
    """Post-stream enrichment (calendar materialize, math fences, …) must not
    abort persistence — the user already saw streamed tokens."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "hello "
        yield "world"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None
    fake_chat.project_id = None

    finalize = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(
            patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True))
        )
        stack.enter_context(
            patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3))
        )
        stack.enter_context(patch("app.services.chat.messages_repo.create", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.chat.build_prompt_messages",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(
            patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False))
        )
        stack.enter_context(
            patch(
                "app.services.chat.calendar_service.load_calendar_for_prompt",
                AsyncMock(return_value=None),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.calendar_service.materialize_calendar_proposals",
                AsyncMock(side_effect=RuntimeError("calendar boom")),
            )
        )
        stack.enter_context(
            patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False))
        )
        stack.enter_context(
            patch(
                "app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.email_service.load_gmail_for_prompt",
                AsyncMock(return_value=None),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.web_search_service.augment_prompt_messages",
                AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
            )
        )
        stack.enter_context(
            patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream)
        )
        stack.enter_context(patch("app.services.chat.quota_service.adjust_usage", AsyncMock()))
        stack.enter_context(patch("app.services.chat.usage_repo.add_tokens", AsyncMock()))
        stack.enter_context(patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()))
        stack.enter_context(patch("app.services.chat.jobs.enqueue", AsyncMock()))
        stack.enter_context(patch("app.services.chat.stream.finalize_stream_turn_db", finalize))

        result: dict[str, object] = {}
        collected: list[str] = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            result=result,
            user=fake_user,
        ):
            collected.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert collected == ["hello ", "world"]
    finalize.assert_awaited()
    assert finalize.await_args.args[2] == "hello world"


@pytest.mark.asyncio
async def test_stream_no_final_content_on_normal_completion(stream_offline_io):
    """`final_content` must NOT be set on a normal (non-cancelled) turn — keep
    `done` payloads small."""
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.calendar_service.is_connected", AsyncMock(return_value=False)),
        patch(
            "app.services.chat.calendar_service.load_calendar_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.services.chat.email_service.is_connected", AsyncMock(return_value=False)),
        patch("app.services.chat.email_service.load_gmail_context", AsyncMock(return_value=None)),
        patch(
            "app.services.chat.email_service.load_gmail_for_prompt", AsyncMock(return_value=None)
        ),
        patch("app.services.chat.messages_repo.recent_user_contents", AsyncMock(return_value=[])),
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(side_effect=lambda msgs, *_a, **_k: (msgs, [])),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.chats_repo.touch_by_id", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        result: dict[str, object] = {}
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="question",
            result=result,
        ):
            pass
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert "final_content" not in result


def test_format_user_profile_block_includes_fields():
    user = MagicMock()
    user.name = "Ada Lovelace"
    user.email = "ada@example.com"
    user.location = "London"
    user.location_enabled = True
    block = format_user_profile_block(user)
    assert "Ada Lovelace" in block
    assert "ada@example.com" in block
    assert "London" in block


def test_format_user_name_only_block_uses_first_name():
    user = MagicMock()
    user.name = "Ada Lovelace"
    block = format_user_name_only_block(user)
    assert "Ada" in block


def test_format_user_name_only_block_missing_name():
    user = MagicMock()
    user.name = "   "
    block = format_user_name_only_block(user)
    assert "not on file" in block


def test_max_output_tokens_for_style_short():
    settings = Settings(max_output_tokens=500)
    assert max_output_tokens_for_style("short", settings) == 400


def test_max_output_tokens_for_style_detailed():
    settings = Settings(max_output_tokens=500)
    assert max_output_tokens_for_style("detailed", settings) == 2200


@pytest.mark.asyncio
async def test_stream_edit_response_yields_tokens():
    from app.services import chat as chat_module

    user_id = uuid4()
    chat_id = uuid4()
    message_id = uuid4()

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"

    fake_message = MagicMock()
    fake_message.id = message_id
    fake_message.role = "user"
    fake_message.created_at = MagicMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    async def fake_stream(*args, **kwargs):
        yield "edited"

    with (
        patch("app.services.chat.SessionLocal", return_value=session),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.get_by_id", AsyncMock(return_value=fake_message)),
        patch(
            "app.services.chat.messages_repo.ids_from_chat_at_or_after",
            AsyncMock(return_value=[message_id]),
        ),
        patch(
            "app.services.chat.attachment_lifecycle.purge_attachments_for_messages",
            AsyncMock(return_value=0),
        ),
        patch("app.services.chat.messages_repo.delete_messages_from", AsyncMock()),
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch(
            "app.services.chat.quota_service.daily_limit_for_user",
            MagicMock(return_value=500_000),
        ),
        patch("app.services.chat.stream_chat_response", fake_stream),
    ):
        tokens = [
            tok
            async for tok in chat_module.stream_edit_response(
                AsyncMock(),
                Settings(max_output_tokens=100),
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                new_content="new question",
            )
        ]

    assert tokens == ["edited"]


@pytest.mark.asyncio
async def test_regenerate_restores_assistant_when_stream_empty():
    """If regenerate deletes the prior assistant but the model returns nothing,
    the old reply is restored so the chat is not left blank."""
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.timezone = None

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = MagicMock()
    fake_last.content = "prior answer"
    fake_last.model = "free-chat"

    fake_last_user = MagicMock()
    fake_last_user.content = "question"

    restore = AsyncMock()

    async def empty_stream(**kwargs):
        if False:
            yield ""

    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.get_last", AsyncMock(return_value=fake_last))
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.get_last_user",
                AsyncMock(return_value=fake_last_user),
            )
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=2))
        )
        stack.enter_context(
            patch(
                "app.services.chat.build_prompt_messages",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.web_search_service.is_vocab_quiz_answer",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.web_search_service.is_places_list_query",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.calendar_service.has_write_access",
                AsyncMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.recent_user_contents",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat._augment_web_and_tools",
                AsyncMock(return_value=([{"role": "system", "content": "sys"}], [], None)),
            )
        )
        stack.enter_context(
            patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True))
        )
        stack.enter_context(patch("app.services.chat.quota_service.refund_usage", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.chat.attachment_lifecycle.purge_attachments_for_messages",
                AsyncMock(),
            )
        )
        stack.enter_context(patch("app.services.chat.messages_repo.delete_message", AsyncMock()))
        stack.enter_context(
            patch("app.services.chat.litellm_gateway.stream_chat_completion", empty_stream)
        )
        stack.enter_context(patch("app.services.chat._restore_regenerate_backup", restore))
        tokens = [
            tok
            async for tok in chat_module.stream_regenerate_response(
                AsyncMock(),
                Settings(max_output_tokens=100),
                user_id=fake_user.id,
                chat_id=MagicMock(),
            )
        ]

    assert tokens == []
    restore.assert_awaited_once()
    backup = restore.await_args.args[2]
    assert backup.content == "prior answer"
    assert backup.model == "free-chat"


@pytest.mark.asyncio
async def test_regenerate_deletes_assistant_before_building_prompt():
    """The prior assistant reply must be deleted before prompt context is built."""
    from app.services import chat as chat_module
    from app.services.chat.turn_prep import ClientGeoContext, TurnPromptBundle

    order: list[str] = []

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.timezone = None

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = MagicMock()
    fake_last.content = "prior answer"
    fake_last.model = "free-chat"

    fake_last_user = MagicMock()
    fake_last_user.content = "question"

    async def track_delete(*_args, **_kwargs):
        order.append("delete")

    async def track_build(*_args, **_kwargs):
        order.append("build")
        return TurnPromptBundle(
            prompt_messages=[{"role": "system", "content": "sys"}],
            meta={},
            instant_reply=None,
            search_sources=[],
            local_places=False,
            max_out=100,
            fallback_models=[],
            minimal_quiz=False,
            minimal_vocab_answer=False,
            active_vocab_turn=False,
            quiz_grade=None,
            geo=ClientGeoContext(
                user_location=None,
                client_lat=None,
                client_lng=None,
                has_geo_fix=False,
                geo_query=False,
                ambiguous_nearby=False,
                local_places=False,
            ),
            local_tz="UTC",
            verified_math=None,
        )

    async def empty_stream(**kwargs):
        if False:
            yield ""

    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.get_last", AsyncMock(return_value=fake_last))
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.get_last_user",
                AsyncMock(return_value=fake_last_user),
            )
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=2))
        )
        stack.enter_context(
            patch(
                "app.services.chat.stream.build_stream_prompt_context",
                side_effect=track_build,
            )
        )
        stack.enter_context(
            patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True))
        )
        stack.enter_context(patch("app.services.chat.quota_service.refund_usage", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.chat.attachment_lifecycle.purge_attachments_for_messages",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.delete_message",
                side_effect=track_delete,
            )
        )
        stack.enter_context(
            patch("app.services.chat.litellm_gateway.stream_chat_completion", empty_stream)
        )
        stack.enter_context(patch("app.services.chat._restore_regenerate_backup", AsyncMock()))
        _ = [
            tok
            async for tok in chat_module.stream_regenerate_response(
                AsyncMock(),
                Settings(max_output_tokens=100),
                user_id=fake_user.id,
                chat_id=MagicMock(),
            )
        ]

    assert order.index("delete") < order.index("build")


@pytest.mark.asyncio
async def test_regenerate_passes_client_geo_to_web_search():
    from app.services import chat as chat_module

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"
    fake_user.timezone = None
    fake_user.locale = "en"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"
    fake_chat.summary = None

    fake_last = MagicMock()
    fake_last.role = "assistant"
    fake_last.id = MagicMock()
    fake_last.content = "old"
    fake_last.model = "free-chat"

    fake_last_user = MagicMock()
    fake_last_user.content = "Best restaurants near me"

    augment = AsyncMock(return_value=([{"role": "system", "content": "sys"}], [], None))

    async def empty_stream(**kwargs):
        if False:
            yield ""

    with ExitStack() as stack:
        for patcher in _offline_session_patches():
            stack.enter_context(patcher)
        for patcher in _quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user))
        )
        stack.enter_context(
            patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat))
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.get_last", AsyncMock(return_value=fake_last))
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.get_last_user",
                AsyncMock(return_value=fake_last_user),
            )
        )
        stack.enter_context(
            patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=2))
        )
        stack.enter_context(
            patch(
                "app.services.chat.build_prompt_messages",
                AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.web_search_service.is_vocab_quiz_answer",
                MagicMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.calendar_service.has_write_access",
                AsyncMock(return_value=False),
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.messages_repo.recent_user_contents",
                AsyncMock(return_value=[]),
            )
        )
        stack.enter_context(patch("app.services.chat._augment_web_and_tools", augment))
        stack.enter_context(
            patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True))
        )
        stack.enter_context(patch("app.services.chat.quota_service.refund_usage", AsyncMock()))
        stack.enter_context(
            patch(
                "app.services.chat.attachment_lifecycle.purge_attachments_for_messages",
                AsyncMock(),
            )
        )
        stack.enter_context(patch("app.services.chat.messages_repo.delete_message", AsyncMock()))
        stack.enter_context(
            patch("app.services.chat.litellm_gateway.stream_chat_completion", empty_stream)
        )
        stack.enter_context(patch("app.services.chat._restore_regenerate_backup", AsyncMock()))
        async for _ in chat_module.stream_regenerate_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            client_location="San Francisco, CA",
            client_latitude=37.77,
            client_longitude=-122.42,
        ):
            pass

    augment.assert_awaited_once()
    assert augment.await_args.kwargs["latitude"] == 37.77
    assert augment.await_args.kwargs["longitude"] == -122.42
    assert augment.await_args.kwargs["user_location"] == "San Francisco, CA"


@pytest.mark.asyncio
async def test_instant_reply_usage_uses_input_output_keys(stream_offline_io):
    """Instant replies must seed usage with ``input``/``output`` — the keys
    ``finalize_stream_turn_db`` reads. ``input_tokens``/``output_tokens`` were
    ignored, so quota fell back to full prompt re-estimation and overcharged."""
    from uuid import uuid4

    from app.services.chat.stream import stream_and_finalize
    from app.services.chat.turn_prep import StreamContext

    captured: dict[str, object] = {}

    async def capture_finalize(_redis, _ctx, assistant_text, usage, _result):
        captured["usage"] = dict(usage)
        captured["assistant_text"] = assistant_text

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "what time is it?"}],
        run_title=False,
        user_message_content="what time is it?",
        reserved_tokens=100,
        max_output_tokens=50,
        instant_reply="It's 3:00 PM.",
        skip_memory_jobs=True,
    )

    result: dict[str, object] = {}
    with (
        patch("app.services.chat.stream.finalize_stream_turn_db", side_effect=capture_finalize),
        patch(
            "app.services.chat.calendar_service.materialize_calendar_proposals",
            AsyncMock(side_effect=lambda *_a, **_k: _a[-1] if _a else "It's 3:00 PM."),
        ),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=None)),
    ):
        tokens: list[str] = []
        async for tok in stream_and_finalize(
            AsyncMock(),
            Settings(max_output_tokens=100),
            ctx,
            should_cancel=None,
            result=result,
        ):
            tokens.append(tok)
        finalize_db = result.get("_finalize_db_task")
        if finalize_db is not None:
            await finalize_db

    assert tokens == ["It's 3:00 PM."]
    assert "usage" in captured
    usage = captured["usage"]
    assert isinstance(usage, dict)
    assert "input" in usage and "output" in usage
    assert "input_tokens" not in usage and "output_tokens" not in usage
    assert usage["input"] == 0
    assert usage["output"] >= 1
