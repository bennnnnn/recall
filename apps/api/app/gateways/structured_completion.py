"""Structured model completion, schema recovery and bounded fallback."""

import asyncio
import json
import logging
from typing import cast, get_args, get_origin

from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import litellm_gateway as gateway
from app.gateways import mock_llm
from app.models.schemas import (
    MEMORY_REPLY_MAX_LENGTH,
    MemoryFactOp,
    MemoryFactUpdateResult,
    MemorySectionItem,
    MemorySectionUpdateResult,
)

logger = logging.getLogger(__name__)


def _list_field_name(schema: type[BaseModel]) -> str | None:
    """Name of the schema's first list-typed field, if any (for bare-list wrapping)."""
    for name, field in schema.model_fields.items():
        ann = field.annotation
        if get_origin(ann) is list or any(get_origin(a) is list for a in get_args(ann)):
            return name
    return None


def _fallback_alias(settings: Settings, primary: str) -> str | None:
    """The alias to retry against when the primary background model is down.

    Returns None when mock mode is on, when no fallback is configured, or when
    the primary IS the fallback (don't retry against itself).
    """
    if mock_llm.should_mock_llm(settings):
        return None
    fb = settings.memory_fallback_model_alias.strip()
    if not fb or fb == primary:
        return None
    return fb


async def _complete_structured_once[T: BaseModel](
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_tokens: int,
    timeout_seconds: float | None = None,
    usage: dict[str, int] | None = None,
) -> T | None:
    """One structured attempt. Raises on provider outage; returns None on bad output."""
    route = gateway.resolve_route(model_alias)
    kwargs = gateway._litellm_kwargs(settings, route)  # ModelUnavailableError if no key
    timeout = (
        settings.background_llm_timeout_seconds if timeout_seconds is None else timeout_seconds
    )
    async with asyncio.timeout(timeout):
        response = await gateway.acompletion(  # provider/network errors propagate for retry
            model=route.model,
            messages=messages,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
    gateway._apply_usage_from_response(usage, response)
    raw = (response.choices[0].message.content or "{}").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        logger.debug("Structured completion: bad JSON for %s", model_alias)
        return None  # call succeeded but output was unparseable — retry won't help
    # Models occasionally return a bare array for a single-list schema; wrap it.
    if isinstance(data, list):
        list_field = gateway._list_field_name(schema)
        if list_field is None:
            logger.debug(
                "Structured completion: bare list returned for %s with no list field",
                schema.__name__,
            )
            return None
        data = {list_field: data}
    try:
        return schema.model_validate(data)
    except Exception:
        if schema is MemoryFactUpdateResult and isinstance(data, dict):
            fact_partial = gateway._parse_memory_facts_partial(data)
            if fact_partial is not None:
                return cast(T, fact_partial)
        if schema is MemorySectionUpdateResult and isinstance(data, dict):
            section_partial = gateway._parse_memory_sections_partial(data)
            if section_partial is not None:
                return cast(T, section_partial)
        logger.debug("Structured completion: validation failed for %s", model_alias)
        return None


def _parse_memory_facts_partial(data: dict[str, object]) -> MemoryFactUpdateResult | None:
    raw_ops = data.get("ops")
    if not isinstance(raw_ops, list):
        return None
    valid: list[MemoryFactOp] = []
    for item in raw_ops:
        if not isinstance(item, dict):
            continue
        try:
            valid.append(MemoryFactOp.model_validate(item))
        except Exception:
            logger.debug("Skipping invalid memory fact op", exc_info=True)
    raw_reply = data.get("reply")
    reply = raw_reply.strip()[:MEMORY_REPLY_MAX_LENGTH] if isinstance(raw_reply, str) else ""
    if not valid and not reply:
        return None
    return MemoryFactUpdateResult(ops=valid, reply=reply)


def _parse_memory_sections_partial(data: dict[str, object]) -> MemorySectionUpdateResult | None:
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list):
        return None
    valid: list[MemorySectionItem] = []
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        try:
            valid.append(MemorySectionItem.model_validate(item))
        except Exception:
            logger.debug("Skipping invalid memory section item", exc_info=True)
    if not valid:
        return None
    return MemorySectionUpdateResult(sections=valid)


async def complete_structured[T: BaseModel](
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_tokens: int = 256,
    timeout_seconds: float | None = None,
    usage: dict[str, int] | None = None,
    allow_fallback: bool = True,
    fallback_on_invalid: bool = False,
) -> T | None:
    if mock_llm.should_mock_llm(settings):
        return None

    fallback = gateway._fallback_alias(settings, model_alias) if allow_fallback else None
    try:
        result = await gateway._complete_structured_once(
            settings=settings,
            model_alias=model_alias,
            messages=messages,
            schema=schema,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            usage=usage,
        )
        if result is not None:
            return result
        if fallback is None or not fallback_on_invalid:
            return None
        logger.warning(
            "Background LLM %s returned invalid structured output; retrying with fallback %s",
            model_alias,
            fallback,
        )
        try:
            return await gateway._complete_structured_once(
                settings=settings,
                model_alias=fallback,
                messages=messages,
                schema=schema,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                usage=usage,
            )
        except Exception:
            logger.exception("Background LLM fallback %s also failed", fallback)
            return None
    except Exception:
        if fallback is None:
            logger.exception("Background LLM %s failed and no fallback configured", model_alias)
            return None
        logger.warning(
            "Background LLM %s unavailable; retrying with fallback %s", model_alias, fallback
        )
        try:
            return await gateway._complete_structured_once(
                settings=settings,
                model_alias=fallback,
                messages=messages,
                schema=schema,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                usage=usage,
            )
        except Exception:
            logger.exception("Background LLM fallback %s also failed", fallback)
            return None
