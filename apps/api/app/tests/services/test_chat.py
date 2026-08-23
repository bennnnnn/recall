from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.prompt_builder import (
    build_prompt_messages,
    format_user_name_only_block,
    format_user_profile_block,
    should_include_profile_email,
)
from app.services.chat.prompt_constants import (
    is_broad_self_question,
    is_learning_progress_question,
    is_lightweight_chat_turn,
    is_writing_deliverable_request,
    needs_rich_context,
)
from app.services.chat.turn_prep import resolve_client_geo
from app.services.context_window import estimate_tokens


def test_resolve_client_geo_ignores_client_when_location_disabled():
    user = MagicMock()
    user.location_enabled = False
    user.location = "Oakland, CA"
    geo = resolve_client_geo(
        user,
        "Where am I",
        client_location="San Francisco, CA",
        client_latitude=37.7,
        client_longitude=-122.4,
    )
    assert geo.user_location is None
    assert geo.client_lat is None
    assert geo.client_lng is None
    assert geo.has_geo_fix is False


def test_resolve_client_geo_uses_client_when_location_enabled():
    user = MagicMock()
    user.location_enabled = True
    user.location = "Oakland, CA"
    geo = resolve_client_geo(
        user,
        "Where am I",
        client_location="Berkeley, CA",
        client_latitude=37.87,
        client_longitude=-122.27,
    )
    assert geo.user_location == "Berkeley, CA"
    assert geo.client_lat == 37.87
    assert geo.client_lng == -122.27
    assert geo.has_geo_fix is True


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

    with (
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.messages.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text="Send an email to my wife",
        )

    system = messages[0]["content"]
    assert "Email and message drafting" in system
    assert "draft immediately" in system.lower()
    assert "cannot send email or SMS" in system.lower() or "Never say you sent" in system


@pytest.mark.asyncio
async def test_build_prompt_includes_comparison_table_hint():
    user = MagicMock()
    user.id = uuid4()
    user.name = "Test User"
    user.email = "test@example.com"
    user.location = None
    user.response_style = "balanced"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None

    with (
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.messages.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text="Python vs java",
        )

    system = messages[0]["content"]
    assert "This turn is a comparison" in system
    assert "| Feature | Option A | Option B |" in system
    assert "do NOT answer as long bullet paragraphs" in system


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Python vs java", True),
        ("python versus Java", True),
        ("compare React and Vue", True),
        ("difference between SQL and NoSQL", True),
        ("which is better, Go or Rust?", True),
        ("tell me about Python", False),
        ("Give me tips on how to master python", False),
        ("roadmap to learn TypeScript", False),
        ("hi", False),
        ("", False),
    ],
)
def test_is_comparison_question(text, expected):
    from app.services.chat.prompt_constants import is_comparison_question

    assert is_comparison_question(text) is expected


def test_format_hints_discourage_tables_for_how_tos():
    from app.services.chat.prompt_constants import (
        INTENT_FORMAT_HINT,
        RESPONSE_FORMAT_HINT,
    )

    for blob in (INTENT_FORMAT_HINT, RESPONSE_FORMAT_HINT):
        assert "roadmap" in blob.lower() or "how-to" in blob.lower()
        assert "NEVER" in blob or "Never" in blob
        assert "pipe table" in blob.lower() or "pipe tables" in blob.lower()


def test_universal_format_baseline_pins_answer_first_and_no_decoration():
    """Balanced/detailed turns must stay answer-first and skip decorative
    headings, emoji, raw URLs, and restating the question. These live in
    UNIVERSAL_FORMAT_BASELINE so they cannot silently drop from the prompt."""
    from app.services.chat.prompt_constants import (
        STYLE_HINTS,
        UNIVERSAL_FORMAT_BASELINE,
    )

    assert "Lead with the answer; explanation after." in UNIVERSAL_FORMAT_BASELINE
    assert "No intro paragraph before the conclusion." in UNIVERSAL_FORMAT_BASELINE
    assert "Never use decorative headings" in UNIVERSAL_FORMAT_BASELINE
    assert "Introduction, Background, Overview, Conclusion" in UNIVERSAL_FORMAT_BASELINE
    assert "Let's dive in" in UNIVERSAL_FORMAT_BASELINE
    assert "Do not decorate with emoji unless the user used them." in UNIVERSAL_FORMAT_BASELINE
    assert "[OpenAI docs](url)" in UNIVERSAL_FORMAT_BASELINE
    assert "not raw URLs" in UNIVERSAL_FORMAT_BASELINE
    assert "Do not restate the question." in UNIVERSAL_FORMAT_BASELINE
    assert "simplest structure" in UNIVERSAL_FORMAT_BASELINE
    assert "do not add sections just to look structured" in UNIVERSAL_FORMAT_BASELINE
    assert "Lead with the answer; explanation after." in STYLE_HINTS["balanced"]


def test_format_hints_include_rich_fence_guidance():
    """The model must be told about callouts, steps, and details fences so
    output is visually clear and attractive — the renderers exist in the app
    but were never mentioned in the prompt."""
    from app.services.chat.prompt_constants import (
        INTENT_FORMAT_HINT,
        RESPONSE_FORMAT_HINT,
    )

    # Callout fences
    assert "```tip" in INTENT_FORMAT_HINT
    assert "```warning" in INTENT_FORMAT_HINT
    # Steps fence for procedures
    assert "```steps" in INTENT_FORMAT_HINT
    # Collapsible details
    assert "```details" in INTENT_FORMAT_HINT
    # Comparison fence for pros/cons
    assert "```comparison" in INTENT_FORMAT_HINT
    # Visual polish guidance in RESPONSE_FORMAT_HINT
    assert "visually clear" in RESPONSE_FORMAT_HINT.lower()
    assert "callout" in RESPONSE_FORMAT_HINT.lower() or "```tip" in RESPONSE_FORMAT_HINT


def test_math_formula_shape_rule_is_unified():
    """Global hints and math-solver hints must agree: inline $ for steps,
    ```math only for standalone display — not contradictory guidance."""
    from app.services.chat.prompt_constants import INTENT_FORMAT_HINT, MATH_SOLVER_HINT

    for blob in (INTENT_FORMAT_HINT, MATH_SOLVER_HINT):
        assert "inline" in blob.lower()
        assert "standalone" in blob.lower()
        # Must not tell the model to put step formulas in ```math fences.
        assert "NEVER indent a ```math fence inside that list item" not in blob
    assert "numbered solution steps" in INTENT_FORMAT_HINT.lower()
    assert "general definition or formula" in INTENT_FORMAT_HINT.lower()
    assert "```answer" in INTENT_FORMAT_HINT
    assert "```steps" in INTENT_FORMAT_HINT
    assert "never use a ```steps fence for math" in INTENT_FORMAT_HINT.lower()
    assert "both sides" in INTENT_FORMAT_HINT.lower()
    assert "F + 3 - 3 = 3 - 3" in INTENT_FORMAT_HINT


def test_math_solver_hint_does_not_overclaim_unverified_scope():
    """Stats/combo/NT/matrix used to be listed as broadly "in scope", and
    geometry few-shots embedded concrete dims that taught inventing measures.
    Gate advanced topics on a verified block; mark sample dims illustrative."""
    from app.services.chat.prompt_constants import INTENT_FORMAT_HINT, MATH_SOLVER_HINT

    lower = MATH_SOLVER_HINT.lower()
    assert "never invent" in lower
    assert "illustrative" in lower
    assert "only when a verified" in lower
    assert "do not claim sympy verification" in lower
    # Must not claim bare "are also in scope" without the verified-block gate.
    assert "are also in scope" not in lower
    assert "never invent geometry" in INTENT_FORMAT_HINT.lower()


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

    with (
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.messages.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(user, uuid4(), Settings())

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

    get_by_id = AsyncMock()

    with (
        patch("app.repositories.chats.get_by_id", get_by_id),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.messages.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        await build_prompt_messages(
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

    with (
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=None)),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.messages.list_recent",
            AsyncMock(return_value=[]),
        ),
    ):
        messages = await build_prompt_messages(user, uuid4(), Settings())

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

    with (
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[AsyncMock(type="preference", text="likes Python")]),
        ),
        patch(
            "app.repositories.messages.list_recent",
            return_value=[AsyncMock(role="user", content="Hi")],
        ),
        patch(
            "app.services.memory.format_memory_block",
            return_value="Known facts:\n- [preference] likes Python",
        ),
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

    assert messages[0]["role"] == "system"
    assert "Biniyam Mecuriaw" in messages[0]["content"]
    # Account email is gated to email/tool intents — omitted on a plain "Hi".
    assert "bmecuriaw@gmail.com" not in messages[0]["content"]
    assert "user-saved notes about themselves" in messages[0]["content"]
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

    out: dict[str, object] = {}

    # Real format: one `## {Label}` header per injected section.
    block = (
        "Known facts about the user:\n\n## Profile\nLives in Addis\n\n## Preferences\nlikes Python"
    )

    with (
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[AsyncMock(type="profile", text="Lives in Addis")]),
        ),
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.format_memory_block",
            return_value=block,
        ),
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
        await build_prompt_messages(user, uuid4(), Settings(), out=out)

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

    out: dict[str, object] = {}

    with (
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.format_memory_block",
            return_value="",
        ),
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
        await build_prompt_messages(user, uuid4(), Settings(), out=out)

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

    with (
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.format_memory_block",
            return_value="",
        ),
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

    with (
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.format_memory_block",
            return_value="",
        ),
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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("How is ur day", False),
        ("how's your day going", False),
        ("tell me a joke", False),
        ("explain photosynthesis", False),
        ("hi", False),
        ("what do you remember about my diet", True),
        ("what's my name", True),
        ("draft an email to my wife", True),
        ("don't forget my preference for tea", True),
        ("What word did I learn today", True),
        ("what words did I study", True),
        ("how many words have I mastered", True),
        ("what's my vocab progress", True),
        ("what's another word for happy", False),
    ],
)
def test_needs_rich_context(text, expected):
    assert needs_rich_context(text) is expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("What word did I learn today", True),
        ("what words did I study", True),
        ("how many words have I mastered", True),
        ("today's lesson", True),
        ("what's another word for happy", False),
        ("tell me a joke", False),
        ("explain photosynthesis", False),
    ],
)
def test_is_learning_progress_question(text, expected):
    assert is_learning_progress_question(text) is expected


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

    with patch("app.repositories.messages.list_recent", return_value=[]):
        messages = await build_prompt_messages(
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
    assert "Recall has two features" not in system
    assert "Recall has two todo features" not in system


@pytest.mark.asyncio
async def test_build_prompt_lightweight_hi_skips_memory_and_integrations():
    """A plain greeting must not pay for memory embed / calendar / web hints."""
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = "San Francisco, CA"
    user.location_enabled = True
    user.response_style = "detailed"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"
    user.custom_instructions = "Always mention my cat Fluffy."

    statuses: list[str] = []

    async def capture_status(phase: str, detail: str | None = None) -> None:
        statuses.append(phase)

    with (
        patch("app.repositories.messages.list_recent", return_value=[]) as recent_mock,
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value="MEMORY SHOULD NOT LOAD"),
        ) as memory_mock,
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value="TODOS SHOULD NOT LOAD"),
        ) as todos_mock,
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False, web_search_enabled=True),
            query_text="hi",
            lightweight=True,
            rich_context=False,
            on_status=capture_status,
        )

    recent_mock.assert_awaited()
    memory_mock.assert_not_awaited()
    todos_mock.assert_not_awaited()
    assert statuses == []
    system = messages[0]["content"]
    assert "Dev" in system
    assert "short social turn" in system
    assert "MEMORY SHOULD NOT LOAD" not in system
    assert "TODOS SHOULD NOT LOAD" not in system
    assert "Fluffy" not in system
    assert "Checking your calendar" not in system
    assert "Gmail" not in system
    assert "web_search" not in system.lower()


@pytest.mark.asyncio
async def test_build_prompt_casual_chitchat_skips_memory_without_phrase_list():
    """Casual chat opts out of rich context systemically — not via greeting allowlist."""
    user = MagicMock()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = "San Francisco, CA"
    user.location_enabled = True
    user.response_style = "balanced"
    user.response_tone = "funny"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"
    user.custom_instructions = "Always mention my cat Fluffy."

    statuses: list[str] = []

    async def capture_status(phase: str, detail: str | None = None) -> None:
        statuses.append(phase)

    with (
        patch("app.repositories.messages.list_recent", return_value=[]) as recent_mock,
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value="MEMORY SHOULD NOT LOAD"),
        ) as memory_mock,
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value="TODOS SHOULD NOT LOAD"),
        ) as todos_mock,
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False, web_search_enabled=True),
            query_text="How is ur day",
            lightweight=False,
            rich_context=False,
            on_status=capture_status,
        )

    recent_mock.assert_awaited()
    memory_mock.assert_not_awaited()
    todos_mock.assert_not_awaited()
    assert statuses == []
    system = messages[0]["content"]
    assert "Dev" in system
    assert "short social turn" not in system
    assert "MEMORY SHOULD NOT LOAD" not in system
    assert "TODOS SHOULD NOT LOAD" not in system
    assert "Fluffy" not in system


class _FakeSessionCM:
    """Keep this unit test off the process-wide asyncpg pool."""

    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_build_prompt_forces_rich_context_when_chat_has_attachment_chunks():
    """A casual follow-up after uploading a PDF may not trigger needs_rich_context,
    but if the chat has indexed attachment chunks, RAG retrieval must still run
    so document follow-ups get context. The prompt builder forces rich_context
    when has_chunks_for_chat is True."""
    user = MagicMock()
    user.id = uuid4()
    user.name = "Dev User"
    user.email = "dev@example.com"
    user.location = None
    user.location_enabled = False
    user.response_style = "balanced"
    user.response_tone = "casual"
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = "UTC"
    user.custom_instructions = None

    rag_block = "ATTACHED DOCUMENT CONTEXT"

    with (
        patch("app.services.chat.prompt_builder.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.prompt_builder.chats_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat_history_rag.embed_query_for_prompt",
            AsyncMock(return_value=None),
        ),
        patch("app.repositories.messages.list_recent", AsyncMock(return_value=[])),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.attachment_chunks.has_chunks_for_chat",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.attachment_rag.retrieve_for_prompt",
            AsyncMock(return_value=rag_block),
        ) as rag_mock,
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=True),
            query_text="what's on page 10?",
            rich_context=False,  # would normally skip RAG, but chunks exist
        )

    system = messages[0]["content"]
    assert rag_block in system
    rag_mock.assert_awaited_once()


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

    learning_block = (
        "Today's learning progress (local calendar day, authoritative):\n"
        "- English · Beginner (vocabulary quiz): 0/5 words mastered today "
        "(not started — 5 left for today's vocabulary quiz)"
    )

    with (
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.projects.load_daily_learning_summary_for_prompt",
            AsyncMock(return_value=learning_block),
        ) as daily_mock,
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value="SHOULD NOT USE"),
        ),
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(
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
async def test_build_prompt_learning_progress_injects_today_words():
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

    today_block = (
        "Words from today's session (authoritative):\n"
        "You ARE connected to the user's Recall Learning class.\n"
        "- English: learned/mastered: apple, book"
    )

    with (
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.get_memory_block",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value="User learning topics:\n### English"),
        ),
        patch(
            "app.services.projects.load_today_learning_words_for_prompt",
            AsyncMock(return_value=today_block),
        ) as today_mock,
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text="What word did I learn today",
            client_timezone="America/Los_Angeles",
        )

    today_mock.assert_awaited_once()
    system = messages[0]["content"]
    assert "apple, book" in system
    assert "You ARE connected" in system
    assert "not connected to their learning" in system.lower() or "ARE connected" in system


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

    with (
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=None),
        ),
    ):
        messages = await build_prompt_messages(
            user,
            uuid4(),
            Settings(),
            minimal_quiz_context=True,
        )

    system = messages[0]["content"]
    assert "Vocabulary format rotation" in system
    assert "vocab_quiz" in system
    assert "Recall has two features" not in system
    assert "Recall has two todo features" not in system
    assert "Web search results" not in system
    assert "Google Calendar" not in system
    assert "Known facts about the user" not in system
    # MATH-BE-034: quiz turns skipped the math guardrails entirely, so any
    # math in a quiz explanation rendered as raw ```latex/```copy. The
    # compact math safety hint now ships on quiz/vocab turns too.
    assert "```answer" in system
    assert "```latex" in system


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

    with (
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=chat),
        ),
        patch(
            "app.services.projects.load_project_quiz_context",
            AsyncMock(return_value="Active vocabulary quiz — project: English"),
        ) as quiz_ctx_mock,
    ):
        messages = await build_prompt_messages(
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
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
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
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
        AsyncMock(return_value=None),
    ):
        assert await _should_minimal_quiz_context(session, chat_id, "A") is False


@pytest.mark.asyncio
async def test_grade_quiz_answer_failure_leaves_rollback_to_grading_service():
    from datetime import UTC, datetime

    from app.services.chat.turn_prep.prepare import _grade_quiz_answer

    user = MagicMock()
    user.id = uuid4()
    quiz_msg = MagicMock()
    quiz_msg.content = (
        '```vocab_quiz\n{"quiz_type":"trivia","word":"History","question":"Which wonder?",'
        '"correct":"A","choices":[{"letter":"A","text":"Colossus"},'
        '{"letter":"B","text":"Pyramid"}]}\n```'
    )
    quiz_msg.created_at = datetime.now(UTC)
    grade_session = AsyncMock()

    class SessionCM:
        async def __aenter__(self):
            return grade_session

        async def __aexit__(self, *_args: object) -> None:
            return None

    get_last = AsyncMock(return_value=quiz_msg)
    with (
        patch("app.services.chat.turn_prep.prepare.SessionLocal", return_value=SessionCM()),
        patch(
            "app.services.chat.quiz_messages.get_last_quiz_assistant",
            get_last,
        ),
        patch(
            "app.services.chat.quiz_messages.count_quiz_letter_answers_since",
            AsyncMock(return_value=1),
        ),
        patch(
            "app.services.chat.turn_prep.prepare.projects_service.apply_deterministic_quiz_answer",
            AsyncMock(side_effect=RuntimeError("neon timeout")),
        ),
    ):
        is_letter, grade = await _grade_quiz_answer(
            user=user,
            chat_id=uuid4(),
            chat_project_id=uuid4(),
            content="A",
            prior_assistant=quiz_msg,
        )

    assert is_letter is True
    assert grade is None
    get_last.assert_not_awaited()
    grade_session.rollback.assert_not_awaited()
    grade_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify_turn_mode_returns_quiz_assistant_row():
    from app.services.chat.turn_prep.mode import _classify_turn_mode

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = uuid4()
    chat.quiz_mode = None
    quiz_msg = MagicMock()
    quiz_msg.content = (
        '```vocab_quiz\n{"quiz_type":"trivia","word":"History","question":"Which wonder?",'
        '"correct":"A","choices":[{"letter":"A","text":"Colossus"},'
        '{"letter":"B","text":"Pyramid"},{"letter":"C","text":"Hanging Gardens"},'
        '{"letter":"D","text":"Lighthouse"}]}\n```'
    )

    with patch(
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
        AsyncMock(return_value=quiz_msg),
    ):
        mode = await _classify_turn_mode(AsyncMock(), chat, "A")

    assert mode.quiz_assistant is quiz_msg
    assert mode.minimal_quiz is True


@pytest.mark.asyncio
async def test_classify_turn_mode_open_ended_vocab_answer_flags_active_vocab_turn():
    """An open-ended vocab answer (sentence/definition, no letter) on a
    project chat whose prior assistant was a vocab prompt must set
    ``active_vocab_turn`` and ``minimal_vocab_answer`` — but NOT
    ``minimal_quiz`` (no letter/fence). This is the gap R-API-012 closes:
    without ``active_vocab_turn`` in the web-search/integration gates, such a
    turn would fire Tavily + calendar/gmail context for a learning answer."""
    from app.services.chat.turn_prep.mode import _classify_turn_mode

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = uuid4()
    chat.quiz_mode = None
    # Prior assistant was an open-ended vocab prompt (vocab_card, no fence).
    quiz_msg = MagicMock()
    quiz_msg.content = (
        "```vocab_card\n**ephemeral** — lasting a very short time.\n\n"
        "Write your own sentence using *ephemeral*.\n```"
    )

    with patch(
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
        AsyncMock(return_value=quiz_msg),
    ):
        mode = await _classify_turn_mode(
            AsyncMock(), chat, "the sunset was ephemeral but beautiful"
        )

    assert mode.active_vocab_turn is True
    assert mode.minimal_vocab_answer is True
    assert mode.minimal_quiz is False


@pytest.mark.asyncio
async def test_classify_turn_mode_letter_on_open_ended_prompt_uses_vocab_answer_path():
    """A letter answer ("A") on an open-ended vocab prompt (no vocab_quiz
    fence) must NOT be classified as ``minimal_quiz`` — QUIZ_ANSWER_HINT
    assumes a fence with choices to grade against, which an open-ended prompt
    lacks. Use the vocab-answer path (``minimal_vocab_answer``) instead:
    VOCAB_CHAT_ANSWER_HINT explicitly treats "random single letters" as wrong.
    R-API-013."""
    from app.services.chat.turn_prep.mode import _classify_turn_mode

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = uuid4()
    chat.quiz_mode = None
    quiz_msg = MagicMock()
    quiz_msg.content = (
        "```vocab_card\n**ephemeral** — lasting a very short time.\n\n"
        "Write your own sentence using *ephemeral*.\n```"
    )

    with patch(
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
        AsyncMock(return_value=quiz_msg),
    ):
        mode = await _classify_turn_mode(AsyncMock(), chat, "A")

    assert mode.active_vocab_turn is True
    assert mode.minimal_vocab_answer is True
    assert mode.minimal_quiz is False


@pytest.mark.asyncio
async def test_classify_turn_mode_letter_on_mcq_fence_stays_minimal_quiz():
    """A letter answer on an MCQ prompt (with vocab_quiz fence) must stay
    ``minimal_quiz`` — QUIZ_ANSWER_HINT is correct here because the fence
    has choices and a correct letter. R-API-013 regression guard."""
    from app.services.chat.turn_prep.mode import _classify_turn_mode

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = uuid4()
    chat.quiz_mode = None
    quiz_msg = MagicMock()
    quiz_msg.content = (
        '```vocab_quiz\n{"quiz_type":"trivia","word":"History","question":"Which wonder?",'
        '"correct":"A","choices":[{"letter":"A","text":"Colossus"},'
        '{"letter":"B","text":"Pyramid"},{"letter":"C","text":"Hanging Gardens"},'
        '{"letter":"D","text":"Lighthouse"}]}\n```'
    )

    with patch(
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
        AsyncMock(return_value=quiz_msg),
    ):
        mode = await _classify_turn_mode(AsyncMock(), chat, "A")

    assert mode.minimal_quiz is True
    assert mode.minimal_vocab_answer is False
    assert mode.active_vocab_turn is True


@pytest.mark.asyncio
async def test_classify_turn_mode_skips_quiz_lookup_without_project():
    from app.services.chat.turn_prep.mode import _classify_turn_mode

    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = None
    chat.quiz_mode = None

    with patch(
        "app.services.chat.quiz_messages.get_last_quiz_assistant",
        AsyncMock(),
    ) as get_last:
        mode = await _classify_turn_mode(AsyncMock(), chat, "explain photosynthesis")

    get_last.assert_not_awaited()
    assert mode.quiz_assistant is None
    assert mode.minimal_quiz is False
    assert mode.active_vocab_turn is False


def test_should_augment_web_and_tools_skips_active_vocab_turn():
    """``active_vocab_turn`` must suppress web/tools augmentation even when
    the turn is not lightweight and not minimal_quiz (open-ended vocab
    answer path). R-API-012."""
    from app.services.chat.turn_prep.mode import _should_augment_web_and_tools

    assert (
        _should_augment_web_and_tools(
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            active_vocab_turn=True,
            day_planning=False,
            ambiguous_nearby=False,
            is_external_calendar_question=False,
            is_external_email_question=False,
        )
        is False
    )
    # Casual explain without math/chem/search must not pay Phase B.
    assert (
        _should_augment_web_and_tools(
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            active_vocab_turn=False,
            day_planning=False,
            ambiguous_nearby=False,
            is_external_calendar_question=False,
            is_external_email_question=False,
        )
        is False
    )
    # Math / search intent still augments.
    assert (
        _should_augment_web_and_tools(
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            active_vocab_turn=False,
            day_planning=False,
            ambiguous_nearby=False,
            is_external_calendar_question=False,
            is_external_email_question=False,
            needs_math=True,
        )
        is True
    )


def test_should_fetch_integrations_skips_casual_explain():
    from app.services.chat.turn_prep.mode import _should_fetch_integrations

    assert (
        _should_fetch_integrations(
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            active_vocab_turn=False,
            rich_context=False,
            day_planning=False,
            is_external_calendar_question=False,
            is_external_email_question=False,
            implies_todos=False,
        )
        is False
    )
    assert (
        _should_fetch_integrations(
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            active_vocab_turn=False,
            rich_context=True,
            day_planning=False,
            is_external_calendar_question=False,
            is_external_email_question=False,
            implies_todos=False,
        )
        is True
    )


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

    load_todos = AsyncMock(return_value=None)

    with (
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch("app.repositories.messages.list_recent", return_value=[]),
        patch(
            "app.services.memory.format_memory_block",
            return_value="",
        ),
        patch(
            "app.services.todos.build_todos_system_section",
            load_todos,
        ),
        patch(
            "app.services.projects.load_projects_for_prompt",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.repositories.chats.get_by_id",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.time_context.format_time_context",
            return_value="LOCAL_TIME_BLOCK",
        ) as format_time,
    ):
        await build_prompt_messages(
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


def test_format_user_profile_block_includes_fields():
    user = MagicMock()
    user.name = "Ada Lovelace"
    user.email = "ada@example.com"
    user.plan = "pro"
    user.location = "London"
    user.location_enabled = True
    user.age = 36
    user.country = "United Kingdom"
    user.job = "Mathematician"
    block = format_user_profile_block(user, include_email=True)
    assert "Ada Lovelace" in block
    assert "ada@example.com" in block
    assert "Plan: pro" in block
    assert "London" in block
    assert "Age: 36" in block
    assert "Country: United Kingdom" in block
    assert "Job: Mathematician" in block


def test_format_user_profile_block_omits_email_by_default():
    user = MagicMock()
    user.name = "Ada"
    user.email = "ada@example.com"
    user.plan = "free"
    user.location = None
    user.location_enabled = False
    user.age = None
    user.country = None
    user.job = None
    block = format_user_profile_block(user)
    assert "ada@example.com" not in block
    assert "Email:" not in block


@pytest.mark.parametrize(
    "text, expected",
    [
        (None, False),
        ("", False),
        ("Hi there", False),
        ("What's my email?", True),
        ("draft an email to my boss", True),
        ("check my inbox", True),
    ],
)
def test_should_include_profile_email(text, expected):
    assert should_include_profile_email(text) is expected


def test_format_user_profile_block_omits_empty_structured_fields():
    user = MagicMock()
    user.name = "Ada"
    user.email = "ada@example.com"
    user.plan = "free"
    user.location = None
    user.location_enabled = False
    user.age = None
    user.country = "  "
    user.job = None
    block = format_user_profile_block(user)
    assert "Plan: free" in block
    assert "Age:" not in block
    assert "Country:" not in block
    assert "Job:" not in block


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
