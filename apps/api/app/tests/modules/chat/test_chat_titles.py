"""Tests for chat title normalization."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.models.schemas import ChatOut
from app.modules.chat.titles import (
    GREETING_CHAT_TITLE,
    finalize_generated_title,
    generate_title,
    is_casual_opener,
    normalize_chat_title,
    sanitize_manual_chat_title,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("New chat", None),
        ("  new chat  ", None),
        ("Untitled", None),
        ("Chat", None),
        ("Valid topic name", "Valid topic name"),
        ('"Quoted title"', "Quoted title"),
        ('"My Trip Plan".', "My Trip Plan"),
        ('"My Trip Plan"!', "My Trip Plan"),
        ("\u201cMy Trip Plan\u201d.", "My Trip Plan"),
        # Markdown emphasis the title model sometimes emits.
        ("**Document Summaries**", "Document Summaries"),
        ("**D**ocument** Summaries", "Document Summaries"),
        ("__Trip Plan__", "Trip Plan"),
        ("*Trip Plan*", "Trip Plan"),
        ("_Trip Plan_", "Trip Plan"),
        ('"**My Trip Plan**"', "My Trip Plan"),
        ("A *great* trip", "A great trip"),
        # Not emphasis: math and identifiers keep their characters.
        ("Solve x*2 = 10", "Solve x*2 = 10"),
        ("my_snake_case notes", "my_snake_case notes"),
        ("ab", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_chat_title(raw: str | None, expected: str | None):
    assert normalize_chat_title(raw) == expected


def test_needs_generated_title():
    from app.modules.chat.titles import needs_generated_title

    assert needs_generated_title(None) is True
    assert needs_generated_title("") is True
    assert needs_generated_title("Untitled") is True
    assert needs_generated_title("Homework") is False


def test_chat_out_preserves_user_chosen_generic_title():
    from datetime import UTC, datetime
    from uuid import uuid4

    out = ChatOut(
        id=uuid4(),
        title="New chat",
        model="auto",
        pinned=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert out.title == "New chat"


def test_chat_out_strips_markdown_emphasis_from_stored_title():
    """Already-persisted `**...**` titles render clean — no migration needed."""
    from datetime import UTC, datetime
    from uuid import uuid4

    out = ChatOut(
        id=uuid4(),
        title="**D**ocument** Summaries",
        model="auto",
        pinned=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert out.title == "Document Summaries"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('  "Pinned note"  ', "Pinned note"),
        ('"My Trip Plan".', "My Trip Plan"),
        ("New chat", "New chat"),
        ("ab", "ab"),
        ("", None),
        ("x" * 81, None),
    ],
)
def test_sanitize_manual_chat_title(raw: str, expected: str | None):
    assert sanitize_manual_chat_title(raw) == expected


def test_search_result_sanitizes_chat_title():
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.models.schemas import SearchResultItem

    item = SearchResultItem(
        chat_id=uuid4(),
        chat_title='"My Trip Plan".',
        content="hi",
        role="user",
        created_at=datetime.now(UTC),
    )
    assert item.chat_title == "My Trip Plan"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("hi", True),
        ("Hi!", True),
        ("good morning", True),
        ("Good morning.", True),
        ("hello there", True),
        ("good morning, help me with physics", False),
        ("What's still open for me to finish tonight?", False),
        ("", False),
    ],
)
def test_is_casual_opener(raw: str, expected: bool):
    assert is_casual_opener(raw) is expected


@pytest.mark.parametrize(
    "raw, user, expected",
    [
        ("Anything", "hi", GREETING_CHAT_TITLE),
        ("Anything", "good morning", GREETING_CHAT_TITLE),
        ("Tonight leftovers", "What's still open?", "Tonight leftovers"),
        ("New chat", "What's still open?", None),
        # Powers show as a book prints them; a decimal power and an exponent letter stay.
        ("Quadratic Equation 3x^2-2x=8", "$3x^{2}-2x=8$", "Quadratic Equation 3x²-2x=8"),
        ("Scientific notation 10^{-3}", "what is 10^-3", "Scientific notation 10⁻³"),
        ("Power rule x^2.5", "derivative of x^2.5", "Power rule x^2.5"),
        ("Powers x^25.5 and 2^10.5", "x^25.5", "Powers x^25.5 and 2^10.5"),
        ("Exponential decay e^{-2t}", "e^(-2t)", "Exponential decay e^{-2t}"),
    ],
)
def test_finalize_generated_title(raw: str, user: str, expected: str | None):
    assert finalize_generated_title(raw, user) == expected


@pytest.mark.asyncio
async def test_generate_title_greeting_skips_model():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch(
        "app.modules.chat.titles.litellm_gateway.complete_text",
        new_callable=AsyncMock,
    ) as complete:
        title = await generate_title(settings, "good morning", "Hello!")
    assert title == GREETING_CHAT_TITLE
    complete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message, model_reads",
    [
        # The keypad's LaTeX: read raw, "3x^{2}" was titled "3x2" (a different expression).
        ("$3x^{2}-2x=8$", "3x^2-2x=8"),
        ("solve $2x^{2}+3x-5=0$ please", "solve 2x^2+3x-5=0 please"),
        ("f^{\\prime}(x) for $x^{3}$", "f'(x) for x^3"),
        # Money keeps its dollar signs: no LaTeX inside.
        ("Car loan: $25,000 at 6% or $30,000?", "Car loan: $25,000 at 6% or $30,000?"),
    ],
)
async def test_generate_title_reads_keypad_maths_as_plain_powers(message: str, model_reads: str):
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch.object(
        litellm_gateway,
        "complete_text",
        new_callable=AsyncMock,
        return_value="Quadratic Equation 3x^2-2x=8",
    ) as complete:
        title = await generate_title(settings, message, "Worked answer.")
    sent = complete.call_args.kwargs["messages"][1]["content"]
    assert sent == model_reads
    assert title == "Quadratic Equation 3x²-2x=8"


@pytest.mark.asyncio
async def test_generate_title_reads_a_shared_files_words_not_its_path_or_padding():
    """A PDF's text came padded with spaces behind a path line, and the chat was titled with
    the user's own words ("3 Quiz Questions From This")."""
    message = (
        "Make me 3 quiz questions from this\n\n"
        "[File: /attachments/039ccfd7-28a8-4fae-a739-cf8210779b1a/file]\n"
        "[File (application/pdf)]\n"
        "[page 1] Chemistry Unit 4 Study Guide - Mr. Patel" + " " * 200 + "\n" + " " * 80 + "\n"
        "Test date: Friday, November 6."
    )
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch.object(
        litellm_gateway,
        "complete_text",
        new_callable=AsyncMock,
        return_value="Chemistry Unit 4 Quiz",
    ) as complete:
        await generate_title(settings, message, "```quiz\n{}\n```")
    sent = complete.call_args.kwargs["messages"][1]["content"]
    assert "/attachments/" not in sent
    assert "  " not in sent
    assert "Chemistry Unit 4 Study Guide - Mr. Patel Test date: Friday" in sent


@pytest.mark.asyncio
async def test_generate_title_never_sends_an_empty_turn_for_a_photo_alone():
    """Review (#2344): a photo-only message is only its path; stripped, the turn was empty."""
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch.object(
        litellm_gateway,
        "complete_text",
        new_callable=AsyncMock,
        return_value="Golden Retriever Photo",
    ) as complete:
        title = await generate_title(
            settings,
            "[Image: /attachments/039ccfd7-28a8-4fae-a739-cf8210779b1a/file]",
            "That's a golden retriever puppy.",
        )
    sent = complete.call_args.kwargs["messages"][1]["content"]
    assert sent.strip()
    assert "/attachments/" not in sent
    assert title == "Golden Retriever Photo"
