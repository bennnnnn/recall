import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from litellm import acompletion

from app.core.config import Settings
from app.gateways import mock_llm
from app.models.schemas import MemoryExtractionResult

logger = logging.getLogger(__name__)

MODEL_ALIAS_MAP: dict[str, str] = {
    "free-chat": "deepseek/deepseek-chat",
    "smart-chat": "deepseek/deepseek-reasoner",
    "title-model": "deepseek/deepseek-chat",
    "memory-model": "deepseek/deepseek-chat",
}


def resolve_model(alias: str) -> str:
    return MODEL_ALIAS_MAP.get(alias, MODEL_ALIAS_MAP["free-chat"])


def _litellm_kwargs(settings: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if settings.deepseek_api_key:
        kwargs["api_key"] = settings.deepseek_api_key
    if settings.openrouter_api_key:
        kwargs["api_key"] = settings.openrouter_api_key
    return kwargs


async def stream_chat_completion(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> AsyncIterator[str]:
    if mock_llm.should_mock_llm(settings):
        logger.info("Using mock LLM stream for alias=%s", model_alias)
        async for token in mock_llm.mock_stream():
            yield token
        return

    model = resolve_model(model_alias)
    kwargs = _litellm_kwargs(settings)
    try:
        response = await acompletion(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            **kwargs,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        yield "[Error: model unavailable. Check API keys and try again.]"


async def complete_structured[T](
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_tokens: int = 256,
) -> T | None:
    if mock_llm.should_mock_llm(settings):
        return None

    model = resolve_model(model_alias)
    kwargs = _litellm_kwargs(settings)
    try:
        response = await acompletion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            **kwargs,
        )
        raw = response.choices[0].message.content or "{}"
        # Strip markdown code fences if model wraps JSON in ```json ... ```
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return schema.model_validate(data)
    except Exception:
        logger.exception("LiteLLM structured completion failed for alias=%s", model_alias)
        return None


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
            "content": "You title conversations in 3-6 words. Reply with ONLY the title.",
        },
        {"role": "user", "content": user_message[:300]},
        {"role": "assistant", "content": assistant_message[:300]},
        {"role": "user", "content": "Title?"},
    ]
    kwargs = _litellm_kwargs(settings)
    try:
        response = await acompletion(
            model=resolve_model("title-model"),
            messages=messages,
            max_tokens=20,
            **kwargs,
        )
        raw = (response.choices[0].message.content or "").strip().strip('"').strip("'")
        # Clamp to schema bounds
        if 3 <= len(raw) <= 80:
            return raw
        return None
    except Exception:
        logger.exception("Title generation failed")
        return None


async def extract_memories(
    settings: Settings,
    transcript: str,
) -> MemoryExtractionResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_memories(transcript)

    messages = [
        {
            "role": "system",
            "content": (
                "Extract durable facts about the user from this conversation. "
                "Return ONLY a JSON object (no markdown): "
                '{"memories": [{"type": "profile|preference|project|fact|focus", '
                '"text": "concise fact in third person", "confidence": 0.0-1.0}]}. '
                "Only extract stable facts worth remembering long-term. "
                "Skip small talk. Return empty memories array if nothing is worth saving."
            ),
        },
        {"role": "user", "content": transcript},
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemoryExtractionResult,
        max_tokens=512,
    )
