import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from litellm import acompletion

from app.core.config import Settings
from app.gateways import mock_llm
from app.models.schemas import MemoryExtractionResult

logger = logging.getLogger(__name__)

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class ModelUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class ModelRoute:
    model: str
    api_key_field: str
    api_base: str | None = None


MODEL_ALIAS_MAP: dict[str, ModelRoute] = {
    "free-chat": ModelRoute("deepseek/deepseek-chat", "deepseek_api_key"),
    "smart-chat": ModelRoute("deepseek/deepseek-reasoner", "deepseek_api_key"),
    "title-model": ModelRoute("deepseek/deepseek-chat", "deepseek_api_key"),
    "memory-model": ModelRoute("deepseek/deepseek-chat", "deepseek_api_key"),
}


def resolve_model(alias: str) -> str:
    return MODEL_ALIAS_MAP.get(alias, MODEL_ALIAS_MAP["free-chat"]).model


def resolve_route(alias: str) -> ModelRoute:
    return MODEL_ALIAS_MAP.get(alias, MODEL_ALIAS_MAP["free-chat"])


def _litellm_kwargs(settings: Settings, route: ModelRoute) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        raise ModelUnavailableError(
            f"No API key configured for model alias (needs {route.api_key_field})."
        )
    kwargs["api_key"] = api_key
    if route.api_base:
        kwargs["api_base"] = route.api_base
    return kwargs


def _apply_usage(usage: dict[str, int] | None, chunk: Any) -> None:
    if usage is None:
        return
    chunk_usage = getattr(chunk, "usage", None)
    if not chunk_usage:
        return
    prompt = getattr(chunk_usage, "prompt_tokens", None)
    completion = getattr(chunk_usage, "completion_tokens", None)
    if prompt is not None:
        usage["input"] = int(prompt)
    if completion is not None:
        usage["output"] = int(completion)


async def stream_chat_completion(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    usage: dict[str, int] | None = None,
) -> AsyncIterator[str]:
    if mock_llm.should_mock_llm(settings):
        logger.info("Using mock LLM stream for alias=%s", model_alias)
        async for token in mock_llm.mock_stream():
            yield token
        return

    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            stream_options={"include_usage": True},
            **kwargs,
        )
        async for chunk in response:
            _apply_usage(usage, chunk)
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except ModelUnavailableError:
        raise
    except Exception as exc:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        raise ModelUnavailableError("Model unavailable. Check API keys and try again.") from exc


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

    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = response.choices[0].message.content or "{}"
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
    route = resolve_route("title-model")
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            max_tokens=20,
            **kwargs,
        )
        raw = (response.choices[0].message.content or "").strip().strip('"').strip("'")
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
