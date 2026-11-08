"""Shared helpers for chat title validation, display, and LLM generation."""

import asyncio
import logging
import re
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.validation import BORING_CHAT_TITLES as BORING_CHAT_TITLES
from app.core.validation import normalize_chat_title as normalize_chat_title
from app.core.validation import normalize_stored_chat_title, unwrap_chat_title
from app.gateways import litellm_gateway, mock_llm
from app.models.routing_lanes import ROUTING
from app.modules.attachments.markers import (
    image_attachment_ids_from_text,
    without_attachment_refs,
)
from app.modules.conversation import service as conversation_service
from app.services.glyphs import SUPERSCRIPT_DIGIT_GLYPHS
from app.services.subject_scan import words_after_scanner_caption
from app.services.symbolic_text import fold_latex_marks, fold_numeric_superscripts
from app.services.text_normalize import collapse_ws

GREETING_CHAT_TITLE = "Greeting"


def title_job_key(chat_id: UUID) -> str:
    """The ``topic`` job's dedupe key: one title per chat, however many ask for it."""
    return f"topic:{chat_id}"


# Exact first-line openers after unwrap + casefold. Longer first messages
# still go to title-model (e.g. "good morning, help me with physics").
_CASUAL_OPENERS = frozenset(
    {
        "hi",
        "hii",
        "hello",
        "hello hello",
        "hey",
        "hey there",
        "hi there",
        "hello there",
        "yo",
        "hiya",
        "howdy",
        "sup",
        "gm",
        "good morning",
        "good afternoon",
        "good evening",
        "good night",
        "morning",
        "evening",
        "thanks",
        "thank you",
        "what's up",
        "whats up",
        "how are you",
        "how's it going",
        "hows it going",
        "hey recall",
        "hi recall",
    }
)

_logger = logging.getLogger(__name__)

# Maths the keypad sends as LaTeX ("$3x^{2}-2x=8$"). Read raw, the title model dropped the
# braces and the caret and titled it "3x2-2x=8", another expression; folded to "3x^2-2x=8"
# first, it keeps the power. Only a dollar span with LaTeX in it is unwrapped: "$25,000" is money.
_DOLLAR_SPAN = re.compile(r"(\${1,2})([^$\n]+?)\1")
_LATEX_INSIDE = re.compile(r"[\\^_{}]")
# A whole-number power, as the title model writes it ("3x^2", "10^{-3}"); "x^2.5" and
# "x^25.5" stay as they are (the digits never back off to make a whole number).
_CARET_POWER = re.compile(r"\^(?:\{(-?\d+)\}|(-?\d+))(?!\d|[.,]\d)")
# The head a title reads, before its padding and paths go: a long paste is not folded whole.
_SOURCE_CHARS = 4000
_NO_WORDS = "(a photo or file, sent with no words)"
_TO_SUPERSCRIPT = str.maketrans("0123456789-", SUPERSCRIPT_DIGIT_GLYPHS + "⁻")


def _own_words(user_message: str) -> str:
    """The user's message as the title model reads it: keypad LaTeX folded to plain powers.

    A shared PDF's text comes padded with runs of spaces, behind a storage-path line: the
    model's 300 characters held "Make me 3 quiz questions from this", a path and blanks, and
    it titled the chat with the user's words. Without the path and the padding, the file's
    own words ("Chemistry Unit 4 Study Guide") fit.

    The scanner's caption ("Solve the math problem in this image step by step.") is the
    app's words, not the student's: read as the ask, a screenshot sent with it was titled
    "No Math Problem Found". Without it, a bare scan is a photo with no words, named by what
    the reply says it shows.
    """
    unwrapped = _DOLLAR_SPAN.sub(
        lambda span: span.group(2) if _LATEX_INSIDE.search(span.group(2)) else span.group(0),
        words_after_scanner_caption(user_message)[:_SOURCE_CHARS],
    )
    readable = collapse_ws(without_attachment_refs(unwrapped))
    return fold_numeric_superscripts(fold_latex_marks(readable))


def _title_source(user_message: str) -> str:
    """The user's words; a photo sent alone is nothing but its path: the reply says what it
    shows, and an empty turn is one a provider may refuse."""
    return _own_words(user_message) or _NO_WORDS


# The name is what the user asked, never what the reply concluded: given the reply as the
# chat's last turn, the title model named chats by their verdict ("Equation No Solution",
# "Arsenal beats Chelsea 2-1") or in stacked nouns ("User Name Inquiry"), and answered
# Spanish and Amharic chats in English. The reply now comes as context inside one turn.
# Every word here is paid on every chat: the whole prompt stays near 500 tokens.
_TITLE_RULES = (
    "Name this chat for a history list. Reply with only the name.\n"
    "Name what the user asked, sent or is doing, never the answer: nothing the reply "
    "concluded (a result, yes or no, a winner, 'no solution', 'not found'). The reply only "
    "shows what the message means, such as what a photo shows.\n"
    "Write it in the language of the user's message.\n"
    "2-6 natural words in sentence case, from the user's side: 'Learning Spanish', never "
    "'Teaching Spanish'. No stacked nouns, no filler (Inquiry, Request, Calculation), never "
    "'user'.\n"
    "Plain text, no quotes, no end punctuation. Maths in symbols (2x + 5 = 17), never in "
    "words. Times, dates and numbers as written (4:14 AM, 3.5%, 300k). No generic label "
    "(New chat, Untitled, Chat).\n"
    "A message that is only a greeting or small talk (hi, how are you) is named Greeting."
)
# Room for six words in any script: a four-word Amharic title is 24 tokens; an unused
# budget costs nothing.
_TITLE_MAX_TOKENS = 64
# What the model reads of the chat: the user's message, and the reply only as context.
_MESSAGE_CHARS = 300
_REPLY_CHARS = 200
# Worked examples the model reads before the chat: a small model follows a shown answer
# more closely than a rule (with rules alone, a photo of an equation was still named
# "Equation with no solution" in half the runs). Each is (message, sent with a photo,
# reply, title): a photo's maths not named by its verdict, a photo named by what it shows
# rather than what it lacked, and another language with its winner left out.
_TITLE_EXAMPLES: tuple[tuple[str, bool, str, str], ...] = (
    (
        _NO_WORDS,
        True,
        "**There is no real solution.** The discriminant of x² + x + 2 = 0 is negative.",
        "Solving x² + x + 2 = 0",
    ),
    (
        _NO_WORDS,
        True,
        "I don't see a math problem here. It's a photo of a cat asleep on a laptop.",
        "Cat asleep on a laptop",
    ),
    (
        "¿quién ganó la final del mundial 2022?",
        False,
        "Argentina ganó la final ante Francia en los penales.",
        "Final del Mundial 2022",
    ),
)


def _title_turn(source: str, *, photo: bool, reply: str) -> str:
    """One chat as the title model reads it: the user's words, then the reply as context."""
    return f"User{' (with a photo)' if photo else ''}: {source}\nReply (context only): {reply}"


def title_messages(user_message: str, assistant_message: str) -> list[dict[str, str]]:
    """The title model's prompt: the rules, the worked examples, then this chat."""
    messages = [{"role": "system", "content": _TITLE_RULES}]
    for source, photo, reply, title in _TITLE_EXAMPLES:
        messages.append({"role": "user", "content": _title_turn(source, photo=photo, reply=reply)})
        messages.append({"role": "assistant", "content": title})
    chat = _title_turn(
        _title_source(user_message)[:_MESSAGE_CHARS],
        photo=bool(image_attachment_ids_from_text(user_message)),
        reply=collapse_ws(assistant_message)[:_REPLY_CHARS],
    )
    # The rule again where a small model reads last.
    messages.append(
        {
            "role": "user",
            "content": f"{chat}\nName what was asked or sent, in the language of the message.",
        }
    )
    return messages


def _superscript_powers(title: str) -> str:
    """Powers as a book prints them, in the drawer: "3x^2 - 2x = 8" → "3x² - 2x = 8"."""
    return _CARET_POWER.sub(
        lambda power: (power.group(1) or power.group(2)).translate(_TO_SUPERSCRIPT), title
    )


def needs_generated_title(title: str | None) -> bool:
    """True when the chat still needs the topic job (empty or a placeholder)."""
    cleaned = unwrap_chat_title(title or "")
    if not cleaned:
        return True
    return cleaned.casefold() in BORING_CHAT_TITLES


def sanitize_manual_chat_title(raw: str) -> str | None:
    """User-chosen title — allow boring labels; trim quotes and enforce length."""
    return normalize_stored_chat_title(raw)


def is_casual_opener(user_message: str) -> bool:
    line = unwrap_chat_title(user_message.strip().split("\n", 1)[0]).casefold()
    return bool(line) and line in _CASUAL_OPENERS


def finalize_generated_title(raw: str | None, user_message: str) -> str | None:
    """Greetings get a topic label; otherwise keep a normalized model title."""
    if is_casual_opener(user_message):
        return GREETING_CHAT_TITLE
    title = normalize_chat_title(raw)
    return _superscript_powers(title) if title else None


async def generate_title(
    settings: Settings,
    user_message: str,
    assistant_message: str,
) -> str | None:
    if is_casual_opener(user_message):
        return GREETING_CHAT_TITLE

    if mock_llm.should_mock_llm(settings):
        return finalize_generated_title(
            await mock_llm.mock_title(_own_words(user_message) or assistant_message),
            user_message,
        )

    raw = await litellm_gateway.complete_text(
        settings=settings,
        model_alias=ROUTING.titles,
        messages=title_messages(user_message, assistant_message),
        max_tokens=_TITLE_MAX_TOKENS,
    )
    if raw is None:
        return None
    return finalize_generated_title(raw, user_message)


async def generate_chat_title(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
    *,
    user_id: UUID,
) -> bool:
    """Title the chat from its first exchange (the ``topic`` job); True when one applied.

    False (nothing usable, or the chat already has a title) leaves the job not done,
    so a later request may try again; the caller says so to the queue.
    """
    if not user_message.strip() or not assistant_message.strip():
        return False
    try:
        title = await asyncio.wait_for(
            generate_title(settings, user_message, assistant_message),
            timeout=15.0,
        )
        title = normalize_chat_title(title)
        if not title:
            return False
        async with SessionLocal() as session:
            applied = await conversation_service.set_title_if_empty(
                session, chat_id, title, user_id=user_id, commit=False
            )
            await session.commit()
        return applied
    except Exception:
        _logger.exception("Topic generation failed for chat_id=%s", chat_id)
        raise
