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


def _title_source(user_message: str) -> str:
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
    # A photo sent alone is nothing but its path: the reply says what it shows, and an empty
    # turn is one a provider may refuse.
    return fold_numeric_superscripts(fold_latex_marks(readable)) or _NO_WORDS


# The name is what the user asked, never what the reply concluded: given the reply as the
# chat's last turn, the title model named chats by their verdict ("Equation No Solution",
# "Arsenal beats Chelsea 2-1") or in stacked nouns ("User Name Inquiry"), and answered
# Spanish and Amharic chats in English. The reply now comes as context inside one turn.
_TITLE_RULES = (
    "You name chats in a chat app's history list. Reply with ONLY the name.\n"
    "The name says what the user asked for or is working on: their question, task or "
    "topic, so they can find the chat again. It names the question, never the answer. "
    "Name it from the user's side ('Learning Spanish', not 'Teaching Spanish').\n"
    "Read the assistant's reply only to understand the message: what a photo or file "
    "shows, which problem it holds. Nothing the reply concluded goes in the name, not even "
    "as a description: no result, no yes or no, no winner or score, no 'no solution', "
    "nothing it could not do or find.\n"
    "A photo or file is named by what it shows or holds, as the reply describes it.\n"
    "At most 6 words, short enough for one line, natural and specific, the way a person "
    "labels a note: 'Planning a weekend in Lisbon', 'Height of the Eiffel Tower', 'Why the "
    "sky is blue'. Reword the message rather than repeating it. Sentence case: a capital "
    "first letter, then capitals only for names. No stacked nouns and no filler words such "
    "as Inquiry, Request, Calculating or Analysis. The user is 'my' or 'I', never 'user' "
    "or 'your'.\n"
    "Write the name in the same language as the user's message.\n"
    "Plain text only: no markdown, no quotes, no ending punctuation. Write maths with "
    "symbols, never in words (2x + 5 = 17, not 2x plus 5 equals 17). Keep times, dates and "
    "numbers exactly as written (4:14 AM, 3.5%, 300k).\n"
    "Never use generic labels like 'New chat', 'Untitled', or 'Chat'.\n"
    "A greeting or small talk (hi, how are you) is named Greeting."
)
# Room for six words in any script: a four-word Amharic title is 24 tokens, cut off at 20.
_TITLE_MAX_TOKENS = 40
# Worked examples the model reads before the real chat: a small model follows a shown
# answer more closely than a rule (with rules alone, a photo of an equation was still named
# "Equation with no solution" in half the runs). Each is a way a title went wrong, put
# right: a photo's maths named by its verdict, a photo named by what it lacked, another
# language and its winner, maths in another language's words (an Amharic power came back
# in English words), the message repeated. Each is (message, sent with a photo, reply,
# title).
_TITLE_EXAMPLES: tuple[tuple[str, bool, str, str], ...] = (
    (
        _NO_WORDS,
        True,
        "**There is no real solution.** The discriminant of x² + x + 2 = 0 is 1 - 8 = -7, "
        "which is negative, so the parabola never crosses the x-axis.",
        "Solving x² + x + 2 = 0",
    ),
    (
        _NO_WORDS,
        True,
        "I don't see a math problem in this photo. It shows a cat asleep on a laptop "
        "keyboard. Send a picture of the problem and I'll work through it.",
        "Cat asleep on a laptop",
    ),
    (
        "¿quién ganó la final del mundial 2022?",
        False,
        "Argentina ganó la final del Mundial 2022 ante Francia en los penales (4-2), tras "
        "un empate 3-3.",
        "Final del Mundial 2022",
    ),
    (
        "combien font 5 puissance 4 ?",
        False,
        "5 puissance 4 = 5 × 5 × 5 × 5 = 625.",  # noqa: RUF001 - a reply's times sign
        "Calcul de 5⁴",
    ),
    (
        "can you help me write a toast for my brother's wedding",
        False,
        "Of course! Here's a warm, short toast you can adapt: ...",
        "Toast for my brother's wedding",
    ),
)


def _title_turn(source: str, *, photo: bool, reply: str) -> str:
    """One chat as the title model reads it: the user's words, then the reply as context."""
    sent_with = " (sent with a photo)" if photo else ""
    return (
        f"The user's message{sent_with}:\n{source}\n\n"
        f"The assistant's reply (context only, never the name):\n{reply}\n\n"
        "Name this chat by what the user asked or sent, not by what the reply concluded, "
        "in the language of the user's message."
    )


def title_messages(user_message: str, assistant_message: str) -> list[dict[str, str]]:
    """The title model's prompt: the rules, the worked examples, then this chat."""
    messages = [{"role": "system", "content": _TITLE_RULES}]
    for source, photo, reply, title in _TITLE_EXAMPLES:
        messages.append({"role": "user", "content": _title_turn(source, photo=photo, reply=reply)})
        messages.append({"role": "assistant", "content": title})
    messages.append(
        {
            "role": "user",
            "content": _title_turn(
                _title_source(user_message)[:300],
                photo=bool(image_attachment_ids_from_text(user_message)),
                reply=collapse_ws(assistant_message)[:300],
            ),
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
            await mock_llm.mock_title(user_message),
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
