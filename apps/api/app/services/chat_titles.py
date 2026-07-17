"""Shared helpers for chat title validation, display, and LLM generation."""

from app.core.config import Settings
from app.core.validation import BORING_CHAT_TITLES as BORING_CHAT_TITLES
from app.core.validation import normalize_chat_title as normalize_chat_title
from app.gateways import litellm_gateway, mock_llm


def sanitize_manual_chat_title(raw: str) -> str | None:
    """User-chosen title — allow boring labels; trim quotes and enforce length."""
    title = raw.strip().strip('"').strip("'").strip()
    if not title or len(title) > 80:
        return None
    return title


async def generate_title(
    settings: Settings,
    user_message: str,
    assistant_message: str,
) -> str | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_title(user_message)

    messages = [
        {
            "role": "system",
            "content": (
                "You title conversations in 3-6 words. Reply with ONLY the title. "
                "Never use generic labels like 'New chat', 'Untitled', or 'Chat'."
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
    return normalize_chat_title(raw.strip().strip('"').strip("'"))
