"""Shared helpers for chat title validation, display, and LLM generation."""

from app.core.config import Settings
from app.core.validation import BORING_CHAT_TITLES as BORING_CHAT_TITLES
from app.core.validation import normalize_chat_title as normalize_chat_title
from app.core.validation import normalize_stored_chat_title, unwrap_chat_title
from app.gateways import litellm_gateway, mock_llm

GREETING_CHAT_TITLE = "Greeting"

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
    return normalize_chat_title(raw)


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
                "Never copy the user's message verbatim. "
                "Never use generic labels like 'New chat', 'Untitled', or 'Chat'. "
                "Greetings (hi, hello, good morning) get a short topic label such as Greeting."
            ),
        },
        {"role": "user", "content": user_message[:300]},
        {"role": "assistant", "content": assistant_message[:300]},
        {"role": "user", "content": "Title?"},
    ]
    raw = await litellm_gateway.complete_text(
        settings=settings,
        model_alias="title-model",
        messages=messages,
        max_tokens=20,
    )
    if raw is None:
        return None
    return finalize_generated_title(raw, user_message)
