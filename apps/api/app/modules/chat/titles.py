"""Shared helpers for chat title validation, display, and LLM generation."""

import asyncio
import logging
import re
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.validation import BORING_CHAT_TITLES as BORING_CHAT_TITLES
from app.core.validation import normalize_chat_title as normalize_chat_title
from app.core.validation import (
    normalize_locale_code,
    normalize_stored_chat_title,
    unwrap_chat_title,
)
from app.gateways import litellm_gateway, mock_llm
from app.models.routing_lanes import ROUTING
from app.modules.attachments.markers import (
    image_attachment_ids_from_text,
    without_attachment_refs,
)
from app.modules.conversation import service as conversation_service
from app.modules.turn_reading.readable import (
    has_english_word,
    has_other_language_word,
    in_other_script,
)
from app.services.glyphs import SUPERSCRIPT_DIGIT_GLYPHS
from app.services.subject_scan import words_after_scanner_caption
from app.services.symbolic_text import fold_latex_marks, fold_numeric_superscripts
from app.services.text_normalize import collapse_ws

GREETING_CHAT_TITLE = "Greeting"


def title_job_key(chat_id: UUID) -> str:
    """The ``topic`` job's dedupe key: one title per chat, however many ask for it."""
    return f"topic:{chat_id}"


def title_job_payload(
    *,
    chat_id: UUID,
    user_id: UUID,
    user_message: str,
    assistant_message: str,
    locale: str | None = None,
) -> dict[str, str]:
    """The ``topic`` job's payload, cut to what the title reads: a stored message holds
    every file's text (up to ten), and none of it past the head ever reaches the model.
    The app language tells the title an English chat from one in another language whose
    words show none ("Erkläre mir die Photosynthese", "2x + 3 = 7")."""
    payload = {
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "user_message": user_message[:TITLE_SOURCE_CHARS],
        "assistant_message": assistant_message[:TITLE_SOURCE_CHARS],
    }
    if isinstance(locale, str) and locale:
        payload["locale"] = locale
    return payload


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
TITLE_SOURCE_CHARS = 4000
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
        words_after_scanner_caption(user_message)[:TITLE_SOURCE_CHARS],
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
    "Write it in the language and script of the user's message, never translated into "
    "English.\n"
    "2-6 natural words in sentence case, from the user's side: 'Learning Spanish', never "
    "'Teaching Spanish'. No stacked nouns, no filler (Inquiry, Request, Calculation), never "
    "'user'.\n"
    "Plain text, no quotes, no end punctuation. Maths in symbols (2x + 5 = 17), never in "
    "words. Times, dates and numbers as written (4:14 AM, 3.5%, 300k). No generic label "
    "(New chat, Untitled, Chat).\n"
    "A message that is only a greeting or small talk (hi, how are you) is named Greeting, "
    "in English whatever its language."
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


def title_messages(
    user_message: str, assistant_message: str, *, locale: str | None = None
) -> list[dict[str, str]]:
    """The title model's prompt: the rules, the worked examples, then this chat."""
    messages = [{"role": "system", "content": _TITLE_RULES}]
    for source, photo, reply, title in _TITLE_EXAMPLES:
        messages.append({"role": "user", "content": _title_turn(source, photo=photo, reply=reply)})
        messages.append({"role": "assistant", "content": title})
    source = _title_source(user_message)
    chat = _title_turn(
        source[:_MESSAGE_CHARS],
        photo=bool(image_attachment_ids_from_text(user_message)),
        reply=collapse_ws(assistant_message)[:_REPLY_CHARS],
    )
    # The rule again where a small model reads last, naming English outright: told only "the
    # message's language", it named one English chat in seven in Spanish, after the example.
    # English only on evidence: an English-language user's words with an English word and none
    # of another language ("Draw a cat"). "Quiero aprender guitarra", "2x + 3 = 7", another app
    # language and a photo with no words leave it open. A job queued without one reads English.
    words = _own_words(user_message)
    english_user = normalize_locale_code(locale or "en") == "en"
    english = english_user and has_english_word(words) and not has_other_language_word(words)
    language = "English" if english else "the message's language and script"
    messages.append(
        {"role": "user", "content": f"{chat}\nName what was asked or sent, in {language}."}
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


def _without_open_mark(title: str) -> str:
    """A model's "¿Qué tal?" loses its "?" in the unwrap; its "¿" goes with it. A pair still
    closed inside ("¿Qué es Python? Guía") stays whole. Only for a model's title: a user's
    own rename keeps what they typed."""
    for opening, closing in ("¿?", "¡!"):
        if title.startswith(opening) and closing not in title:
            title = title[1:].strip()
    return title


# "User" opening a title the user never wrote that word in: the chat in the third person, as a
# profile note ("User is vegetarian" for "Remember that I am vegetarian"). The rules say
# never "user", and the title model wrote it every time it was told to remember something.
# A message about users keeps it ("User interface design", "User is not defined error").
_USER_FIRST = re.compile(r"^(?:the\s+)?users?\b", re.IGNORECASE)
_USER_WORD = re.compile(r"\busers?\b", re.IGNORECASE)


def _in_message_script(title: str, user_message: str) -> bool:
    """A title in the script of the user's words: an Amharic lesson was named in English. The
    script is the evidence, never a list of words: names and loanwords ("Schrödinger", "Las
    Vegas", "café") are English titles' too. A photo with no words keeps the model's name."""
    words = _own_words(user_message)
    return not words or in_other_script(title) == in_other_script(words)


def _speaks_of_the_user(title: str, user_message: str) -> bool:
    return bool(_USER_FIRST.match(title)) and not _USER_WORD.search(_own_words(user_message))


def finalize_generated_title(raw: str | None, user_message: str) -> str | None:
    """Greetings get a topic label; otherwise keep a normalized model title in the message's
    language (another is rejected: the user's own words name the chat instead)."""
    if is_casual_opener(user_message):
        return GREETING_CHAT_TITLE
    title = normalize_chat_title(raw)
    title = normalize_chat_title(_without_open_mark(title)) if title else None
    if title and (
        _speaks_of_the_user(title, user_message) or not _in_message_script(title, user_message)
    ):
        return None
    return _superscript_powers(title) if title else None


# A fallback name is the user's first words, as many as a title holds.
_FALLBACK_WORDS = 6
_FALLBACK_CHARS = 60


def fallback_title(user_message: str) -> str:
    """The name a chat gets when the model's is rejected (empty, a label like "Title", too
    short or too long): the user's own first words. Left unnamed, the chat was read again
    and titled again every 5 minutes (the message-page backfill), paying a call each time.

    Words too few to name anything ("Sí", "ok") are small talk: Greeting. A photo or file
    with no words is Photo or File.
    """
    words = _own_words(user_message).split()
    if not words:
        return "Photo" if image_attachment_ids_from_text(user_message) else "File"
    head = words[0]
    for word in words[1:_FALLBACK_WORDS]:
        if len(head) + 1 + len(word) > _FALLBACK_CHARS:
            break
        head = f"{head} {word}"
    head = head[:_FALLBACK_CHARS]
    if words[0].isalpha() and words[0].islower():
        head = head[0].upper() + head[1:]
    return normalize_chat_title(head) or GREETING_CHAT_TITLE


async def generate_title(
    settings: Settings,
    user_message: str,
    assistant_message: str,
    *,
    locale: str | None = None,
) -> str | None:
    if is_casual_opener(user_message):
        return GREETING_CHAT_TITLE

    if mock_llm.should_mock_llm(settings):
        return finalize_generated_title(
            await mock_llm.mock_title(_own_words(user_message) or assistant_message),
            user_message,
        ) or fallback_title(user_message)

    raw = await litellm_gateway.complete_text(
        settings=settings,
        model_alias=ROUTING.titles,
        messages=title_messages(user_message, assistant_message, locale=locale),
        max_tokens=_TITLE_MAX_TOKENS,
    )
    if raw is None:
        # The provider failed: a later request may ask again.
        return None
    # One call per chat: a rejected name falls back to the user's words, never another call.
    return finalize_generated_title(raw, user_message) or fallback_title(user_message)


async def generate_chat_title(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
    *,
    user_id: UUID,
    locale: str | None = None,
) -> bool:
    """Title the chat from its first exchange (the ``topic`` job); True when one applied.

    False (nothing usable, or the chat already has a title) leaves the job not done,
    so a later request may try again; the caller says so to the queue.
    """
    if not user_message.strip() or not assistant_message.strip():
        return False
    try:
        title = await asyncio.wait_for(
            generate_title(settings, user_message, assistant_message, locale=locale),
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
