import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.config import Settings

logger = logging.getLogger(__name__)

MOCK_REPLY = (
    "I'm Recall (mock mode). Wire your DeepSeek/OpenRouter API key in apps/api/.env "
    "to get real responses. Memory, history, and quotas still work end-to-end."
)


def should_mock_llm(settings: Settings) -> bool:
    has_key = bool(settings.deepseek_api_key or settings.openrouter_api_key)
    return settings.mock_llm_enabled and not has_key


async def mock_stream(text: str = MOCK_REPLY) -> AsyncIterator[str]:
    for word in text.split(" "):
        yield word + " "
        await asyncio.sleep(0.03)


async def mock_title(user_message: str) -> str:
    words = user_message.strip().split()[:4]
    return " ".join(words) if words else "New chat"


async def mock_memories(user_message: str):
    from app.models.schemas import MemoryExtractionItem, MemoryExtractionResult

    if len(user_message.strip()) < 10:
        return None
    return MemoryExtractionResult(
        memories=[
            MemoryExtractionItem(
                type="focus",
                text=f"Recently discussed: {user_message[:120]}",
                confidence=0.6,
            )
        ]
    )
