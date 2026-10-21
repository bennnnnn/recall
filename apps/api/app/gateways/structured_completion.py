"""Structured model completion, schema recovery and bounded fallback.

Output that does not parse or fit its schema is never used. It is logged at
WARNING with the alias and the schema, and counted per UTC day in Redis
(``structured_invalid:<day>``, one field per alias and schema), so a model that
starts returning bad JSON shows up instead of silently dropping work.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import cast, get_args, get_origin

from pydantic import BaseModel

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.core.redis import get_redis_client
from app.core.redis_counters import hincr_with_ttl
from app.gateways import llm_spend, mock_llm
from app.gateways.model_output import parse_model_json
from app.models.schemas import (
    MEMORY_REPLY_MAX_LENGTH,
    MemoryFactOp,
    MemoryFactUpdateResult,
    MemorySectionItem,
    MemorySectionUpdateResult,
)

logger = logging.getLogger(__name__)

# A day's counts outlive it long enough to read yesterday's, then expire.
_INVALID_COUNT_TTL_SECONDS = 60 * 60 * 48
_INVALID_COUNT_TIMEOUT_SECONDS = 2.0


def invalid_output_key(day: datetime | None = None) -> str:
    return f"structured_invalid:{(day or datetime.now(UTC)).date().isoformat()}"


def _invalid_output(model_alias: str, schema: type[BaseModel], reason: str) -> None:
    """Log and count one structured reply that was thrown away."""
    logger.warning(
        "Structured completion: %s alias=%s schema=%s", reason, model_alias, schema.__name__
    )
    create_background_task(
        _count_invalid(f"{model_alias}:{schema.__name__}"), name="structured_invalid"
    )


async def _count_invalid(field: str) -> None:
    try:
        async with asyncio.timeout(_INVALID_COUNT_TIMEOUT_SECONDS):
            await hincr_with_ttl(
                get_redis_client(), invalid_output_key(), field, 1, _INVALID_COUNT_TTL_SECONDS
            )
    except Exception:
        logger.debug("structured invalid count not recorded field=%s", field, exc_info=True)


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
    # Imported at call time: litellm_gateway re-exports this module.
    from app.gateways import litellm_gateway as gateway

    route = gateway.resolve_route(model_alias)
    # No thinking pass: a reasoning model can spend the whole max_tokens on it.
    kwargs = gateway._litellm_kwargs(settings, route, thinking=False)  # no key: ModelUnavailable
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
    gateway._apply_usage(usage, response)
    llm_spend.meter_model_call(model_alias, response)
    try:
        data = parse_model_json(response.choices[0].message.content or "{}")
    except ValueError:
        _invalid_output(model_alias, schema, "bad JSON")
        return None  # the call succeeded; only fallback_on_invalid asks again
    # Models occasionally return a bare array for a single-list schema; wrap it.
    if isinstance(data, list):
        list_field = _list_field_name(schema)
        if list_field is None:
            _invalid_output(model_alias, schema, "bare list for a schema with no list field")
            return None
        data = {list_field: data}
    try:
        return schema.model_validate(data)
    except Exception:
        if schema is MemoryFactUpdateResult and isinstance(data, dict):
            fact_partial = _parse_memory_facts_partial(data)
            if fact_partial is not None:
                return cast(T, fact_partial)
        if schema is MemorySectionUpdateResult and isinstance(data, dict):
            section_partial = _parse_memory_sections_partial(data)
            if section_partial is not None:
                return cast(T, section_partial)
        _invalid_output(model_alias, schema, "schema validation failed")
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
    """One structured reply, validated against ``schema``; None when there is none.

    ``allow_fallback``: a provider failure asks the background fallback model once.
    ``fallback_on_invalid``: so does output that does not parse or validate, even
    with ``allow_fallback`` off (a foreground caller keeps its own deadline).
    """
    if mock_llm.should_mock_llm(settings):
        return None
    fallback = _fallback_alias(settings, model_alias)

    async def ask(alias: str) -> T | None:
        return await _complete_structured_once(
            settings=settings,
            model_alias=alias,
            messages=messages,
            schema=schema,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            usage=usage,
        )

    async def ask_fallback(alias: str) -> T | None:
        try:
            return await ask(alias)
        except Exception:
            logger.exception("Background LLM fallback %s also failed", alias)
            return None

    try:
        result = await ask(model_alias)
    except Exception:
        if fallback is None or not allow_fallback:
            logger.exception("Background LLM %s failed and no fallback configured", model_alias)
            return None
        logger.warning(
            "Background LLM %s unavailable; retrying with fallback %s", model_alias, fallback
        )
        return await ask_fallback(fallback)
    if result is not None or fallback is None or not fallback_on_invalid:
        return result
    logger.warning(
        "Background LLM %s returned invalid %s; retrying with fallback %s",
        model_alias,
        schema.__name__,
        fallback,
    )
    return await ask_fallback(fallback)
