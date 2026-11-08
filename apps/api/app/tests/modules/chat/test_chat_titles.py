"""Tests for chat title normalization."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.models.schemas import ChatOut
from app.modules.chat import titles
from app.modules.chat.titles import (
    GREETING_CHAT_TITLE,
    finalize_generated_title,
    generate_title,
    is_casual_opener,
    normalize_chat_title,
    sanitize_manual_chat_title,
    title_messages,
)
from app.services.subject_scan import SCAN_CONFIRMED_PREFIX, SCANNER_CAMERA_PROMPTS

_PHOTO = "[Image: /attachments/039ccfd7-28a8-4fae-a739-cf8210779b1a/file]"
_FILE = "[File: /attachments/039ccfd7-28a8-4fae-a739-cf8210779b1a/file]"


def _chat_turn(messages: list[dict[str, str]]) -> str:
    """The turn that holds the chat being named: the last one, after the worked examples."""
    assert messages[-1]["role"] == "user"
    return messages[-1]["content"]


def _words_read(messages: list[dict[str, str]]) -> str:
    """The user's words as the title model read them, from the chat's turn."""
    _, _, rest = _chat_turn(messages).partition(": ")
    return rest.split("\nReply (context only): ", 1)[0]


def _reply_read(messages: list[dict[str, str]]) -> str:
    """The reply as the title model read it, from the chat's turn."""
    return _chat_turn(messages).split("\nReply (context only): ", 1)[1].split("\n", 1)[0]


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
        # Two letters of a script past Latin are a word: Amharic "news", Chinese "greeting".
        ("ዜና", "ዜና"),
        ("问候", "问候"),
        # Junk stays out: one letter, digits, marks.
        ("ዜ", None),
        ("42", None),
        ("??", None),
        ("a.", None),
        # Spanish opens what its closing mark ends: both go.
        ("¿Qué tal?", "Qué tal"),
        ("¡Feliz cumpleaños!", "Feliz cumpleaños"),
        ('"¿Final del Mundial 2022?"', "Final del Mundial 2022"),
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
    assert _words_read(complete.call_args.kwargs["messages"]) == model_reads
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
    sent = _words_read(complete.call_args.kwargs["messages"])
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
        title = await generate_title(settings, _PHOTO, "That's a golden retriever puppy.")
    sent = _words_read(complete.call_args.kwargs["messages"])
    assert sent.strip()
    assert "/attachments/" not in sent
    assert title == "Golden Retriever Photo"


@pytest.mark.asyncio
async def test_generate_title_reads_the_reply_as_context_not_as_the_chats_last_turn():
    """Given the reply as the chat's last turn, the model named chats by its verdict
    ("Equation No Solution"): the reply now sits under the user's words, as context."""
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch.object(
        litellm_gateway, "complete_text", new_callable=AsyncMock, return_value="Asking my name"
    ) as complete:
        title = await generate_title(settings, "What is my name", "Your name is **bini**.")
    messages = complete.call_args.kwargs["messages"]
    turn = _chat_turn(messages)
    assert turn.index("What is my name") < turn.index("Your name is **bini**.")
    assert "context only" in turn
    # The real reply is never an assistant turn: those are the worked examples' titles.
    assert all("bini" not in m["content"] for m in messages if m["role"] == "assistant")
    # Six words in any script fit: a four-word Amharic title is 24 tokens.
    assert complete.call_args.kwargs["max_tokens"] >= 64
    assert title == "Asking my name"


@pytest.mark.parametrize("caption", list(SCANNER_CAMERA_PROMPTS.values()))
def test_title_reads_a_bare_scan_as_a_photo_with_no_words(caption: str):
    """The scanner's caption is the app's words: read as the ask, a screenshot sent with it
    was titled "No Math Problem Found"."""
    messages = title_messages(f"{caption}\n\n{_PHOTO}", "It shows a settings panel.")
    assert _words_read(messages) == titles._NO_WORDS
    assert "(with a photo)" in _chat_turn(messages)


def test_title_reads_a_scans_confirmed_reading_as_the_problem():
    """The reading is the student's problem; "I read this as:" is the app's words."""
    caption = SCANNER_CAMERA_PROMPTS["math"]
    message = f"{caption}\n\n{SCAN_CONFIRMED_PREFIX} 2x+7=15\n\n{_PHOTO}"
    assert _words_read(title_messages(message, "x = 4")) == "2x+7=15"


@pytest.mark.parametrize(
    "message, photo",
    [
        (_PHOTO, True),
        (f"When is my chemistry test?\n\n{_PHOTO}", True),
        # A file's own text stays in the words, so it needs no mark of its own.
        (f"Summarize this\n\n{_FILE}\n[page 1] Unit 4 study guide", False),
        ("what's 15% of 240", False),
    ],
)
def test_title_says_when_a_photo_came_with_the_message(message: str, photo: bool):
    assert ("(with a photo)" in _chat_turn(title_messages(message, "Reply."))) is photo


def test_title_reads_300_characters_of_the_message_and_200_of_the_reply():
    """Every word the title model reads is paid on every chat: the chat is cut to 500."""
    messages = title_messages("plan my trip " * 60, "Here is a plan. " * 60)
    assert len(_words_read(messages)) == 300
    assert len(_reply_read(messages)) == 200


def test_title_prompt_stays_near_500_tokens():
    """Rules, worked examples and the longest chat in under 2,000 characters (about 500
    tokens of English): one call per chat, at about half the first version's size."""
    messages = title_messages("word " * 200, "reply " * 200)
    assert sum(len(m["content"]) for m in messages) <= 2000
    assert len(titles._TITLE_EXAMPLES) <= 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message, reply, title",
    [
        # A scan in dev's mock mode: the caption is the app's, so the reply names it.
        (
            f"{SCANNER_CAMERA_PROMPTS['math']}\n\n{_PHOTO}",
            "That's a cat on a laptop.",
            "That's a cat on",
        ),
        # A confirmed reading is the student's problem, without the app's prefix.
        (
            f"{SCANNER_CAMERA_PROMPTS['math']}\n\n{SCAN_CONFIRMED_PREFIX} 2x+7=15",
            "x = 4",
            "2x+7=15",
        ),
        ("plan my week please", "Here's a plan.", "plan my week please"),
    ],
)
async def test_mock_titles_read_the_users_own_words(message: str, reply: str, title: str):
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    assert await generate_title(settings, message, reply) == title


def test_title_worked_examples_are_titles_the_rules_allow():
    """Each example the model reads first is a user turn and the title it should get: a
    title the drawer keeps as written, short enough for one line."""
    messages = title_messages("Plan my week", "Here's a plan.")
    examples = messages[1:-1]
    assert [m["role"] for m in examples] == ["user", "assistant"] * len(titles._TITLE_EXAMPLES)
    for _, _, reply, title in titles._TITLE_EXAMPLES:
        assert normalize_chat_title(title) == title
        assert len(title) <= 32
        # The example shows the reply as context only: its title is no line of the reply.
        assert title.casefold() not in {line.strip().casefold() for line in reply.split(".")}
