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
from app.modules.attachments.markers import without_attachment_refs
from app.modules.conversation import service as conversation_service
from app.services.glyphs import SUPERSCRIPT_DIGIT_GLYPHS
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
# A whole-number power, as the title model writes it ("3x^2", "10^{-3}"); "x^2.5" stays as is.
_CARET_POWER = re.compile(r"\^(?:\{(-?\d+)\}|(-?\d+))(?![.,]\d)")
_TO_SUPERSCRIPT = str.maketrans("0123456789-", SUPERSCRIPT_DIGIT_GLYPHS + "⁻")


def _title_source(user_message: str) -> str:
    """The user's message as the title model reads it: keypad LaTeX folded to plain powers.

    A shared PDF's text comes padded with runs of spaces, behind a storage-path line: the
    model's 300 characters held "Make me 3 quiz questions from this", a path and blanks, and
    it titled the chat with the user's words. Without the path and the padding, the file's
    own words ("Chemistry Unit 4 Study Guide") fit.
    """
    unwrapped = _DOLLAR_SPAN.sub(
        lambda span: span.group(2) if _LATEX_INSIDE.search(span.group(2)) else span.group(0),
        user_message,
    )
    readable = collapse_ws(without_attachment_refs(unwrapped))
    return fold_numeric_superscripts(fold_latex_marks(readable))


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

    messages = [
        {
            "role": "system",
            "content": (
                "You title conversations in 3-6 words. Reply with ONLY the title. "
                "Plain text only — no markdown, no asterisks, no quotes. "
                "Never copy the user's message verbatim. "
                "Never use generic labels like 'New chat', 'Untitled', or 'Chat'. "
                "Keep times, dates and numbers exactly as written (4:14 AM, 3.5%, 300k). "
                "Greetings (hi, hello, good morning) get a short topic label such as Greeting."
            ),
        },
        {"role": "user", "content": _title_source(user_message)[:300]},
        {"role": "assistant", "content": collapse_ws(assistant_message)[:300]},
        {"role": "user", "content": "Title?"},
    ]
    raw = await litellm_gateway.complete_text(
        settings=settings,
        model_alias=ROUTING.titles,
        messages=messages,
        max_tokens=20,
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
