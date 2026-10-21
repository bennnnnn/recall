import asyncio
import logging
from collections.abc import AsyncIterator
from typing import cast, get_args

from app.core.config import Settings
from app.core.validation import normalize_chat_title

logger = logging.getLogger(__name__)

MOCK_REPLY = (
    "I'm Recall (mock mode). Add OPENROUTER_API_KEY in apps/api/.env "
    "to get real responses. Memory, history, and quotas still work end-to-end."
)


def should_mock_llm(settings: Settings) -> bool:
    has_key = bool(settings.openrouter_api_key)
    return settings.mock_llm_enabled and not has_key


# 1x1 PNG — valid image bytes for mock image generation in dev.
_MOCK_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def mock_image_bytes() -> bytes:
    return _MOCK_PNG_BYTES


def _last_user_text(messages: list[dict[str, str]] | None) -> str:
    if not messages:
        return ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "").strip()
    return ""


def mock_reply_for_messages(messages: list[dict[str, str]] | None) -> str:
    _ = messages
    return MOCK_REPLY


async def mock_stream(
    text: str | None = None,
    *,
    messages: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    reply = text if text is not None else mock_reply_for_messages(messages)
    for word in reply.split(" "):
        yield word + " "
        await asyncio.sleep(0.03)


async def mock_complete_with_tools(
    *,
    messages: list[dict],
    tools: list[dict],
) -> dict:
    """Dev mock: one web_search tool call when the user asks to search, else no tools."""
    _ = tools
    last = _last_user_text(messages).lower()
    if any(m.get("role") == "tool" for m in messages):
        return {"content": MOCK_REPLY, "tool_calls": []}
    if "search" in last or "look up" in last or "latest" in last:
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": "mock_web_search_1",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query": "mock search"}',
                    },
                }
            ],
        }
    return {"content": MOCK_REPLY, "tool_calls": []}


async def mock_title(user_message: str) -> str | None:
    words = user_message.strip().split()[:4]
    if not words:
        return None
    return normalize_chat_title(" ".join(words))


async def mock_memory_facts(user_message: str, existing_facts: list[dict[str, str]]):
    from app.models.schemas import MemoryFactOp, MemoryFactUpdateResult

    del existing_facts
    if len(user_message.strip()) < 10:
        return None
    return MemoryFactUpdateResult(
        ops=[
            MemoryFactOp(
                op="add",
                type="focus",
                text=f"Recently discussed: {user_message[:200]}",
                confidence=0.6,
                sensitivity="normal",
                importance=0.4,
            )
        ]
    )


async def mock_merge_memory_section(section_type: str, prior_text: str):
    from app.models.schemas import MemorySectionItem, MemoryType

    valid_memory_types = frozenset(get_args(MemoryType))
    sentences = [part.strip() for part in prior_text.split(".") if part.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    summary = ". ".join(unique).strip()
    if summary and not summary.endswith("."):
        summary += "."
    return MemorySectionItem(
        type=cast(
            MemoryType,
            section_type if section_type in valid_memory_types else "fact",
        ),
        summary=summary or prior_text[:300],
        confidence=0.9,
    )


async def mock_summary(prior_summary: str | None, messages: list[dict[str, str]]) -> str:
    snippets = "; ".join(m.get("content", "")[:40] for m in messages[:3] if m.get("content"))
    base = f"{prior_summary} " if prior_summary else ""
    return (base + f"Earlier the user and assistant discussed: {snippets}.").strip()
