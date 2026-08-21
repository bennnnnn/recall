"""Compatibility facade for chat turn orchestration.

Focused implementations live in ``turn_resources``, ``stream_entry``, and
``stream_pipeline``. They receive this module as a seam provider so existing
imports and ``app.services.chat.stream.*`` monkeypatches remain effective.
"""

import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.background_tasks import create_background_task as create_background_task
from app.core.config import Settings
from app.core.db import SessionLocal as SessionLocal
from app.core.ids import uuid7 as uuid7
from app.core.redis_lock import (
    acquire_lock as acquire_lock,
)
from app.core.redis_lock import (
    refresh_lock as refresh_lock,
)
from app.core.redis_lock import (
    release_lock as release_lock,
)
from app.gateways import litellm_gateway as litellm_gateway
from app.models.orm import User
from app.repositories import chats, messages, users
from app.services import attachment_lifecycle as attachment_lifecycle
from app.services import (
    calendar,
    image_generation,
    math_fence,
    plan,
    quota,
    todos,
    web_search,
)
from app.services import model_catalog as model_catalog
from app.services.chat import stream_entry as _entry
from app.services.chat import stream_pipeline as _pipeline
from app.services.chat import turn_resources as _resources
from app.services.chat.finalize_registry import (
    mark_pending_finalize as mark_pending_finalize,
)
from app.services.chat.finalize_registry import (
    register_pending_finalize as register_pending_finalize,
)
from app.services.chat.finalize_registry import (
    wait_for_pending_finalize as wait_for_pending_finalize,
)
from app.services.chat.post_turn import (
    enqueue_post_turn_jobs as enqueue_post_turn_jobs,
)
from app.services.chat.post_turn import (
    finalize_stream_turn_db as finalize_stream_turn_db,
)
from app.services.chat.post_turn import (
    restore_regenerate_backup as restore_regenerate_backup,
)
from app.services.chat.post_turn import (
    seed_usage_from_db as seed_usage_from_db,
)
from app.services.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.services.chat.quality import detect_quality_issues as detect_quality_issues
from app.services.chat.turn_prep import (
    StreamContext,
)
from app.services.chat.turn_prep import (
    build_stream_prompt_context as build_stream_prompt_context,
)
from app.services.chat.turn_prep import (
    count_image_attachments as count_image_attachments,
)
from app.services.chat.turn_prep import (
    prepare_chat_turn as prepare_chat_turn,
)
from app.services.chat.turn_prep import (
    stream_context_from_bundle as stream_context_from_bundle,
)
from app.services.chat.turn_prep import (
    vision_reserve_tokens as vision_reserve_tokens,
)
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.context_window import estimate_tokens as estimate_tokens
from app.services.image_gen_intent import (
    extract_image_gen_prompt as extract_image_gen_prompt,
)
from app.services.image_gen_intent import (
    extract_image_revision_prompt as extract_image_revision_prompt,
)
from app.services.image_gen_intent import (
    image_gen_revision_context as image_gen_revision_context,
)

chats_repo = chats
messages_repo = messages
users_repo = users
calendar_service = calendar
image_generation_service = image_generation
math_fence_service = math_fence
plan_service = plan
quota_service = quota
todos_service = todos
web_search_service = web_search

_CHATPREP_LOCK_TTL_SECONDS = _resources.CHATPREP_LOCK_TTL_SECONDS
_CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS = _resources.CHATPREP_LOCK_REFRESH_INTERVAL_SECONDS
TurnResources = _resources.TurnResources


def _seams():
    return sys.modules[__name__]


@asynccontextmanager
async def turn_resources(
    redis: Redis,
    *,
    user_id: UUID,
    chat_id: UUID,
    borrowed: TurnResources | None = None,
) -> AsyncIterator[TurnResources]:
    async with _resources.turn_resources(
        _seams(),
        redis,
        user_id=user_id,
        chat_id=chat_id,
        borrowed=borrowed,
    ) as resources:
        yield resources


async def _yield_with_chatprep_refresh(
    redis: Redis,
    lock_key: str,
    lock_token: str,
    tokens: AsyncIterator[str],
) -> AsyncIterator[str]:
    async for token in _resources.yield_with_chatprep_refresh(
        _seams(), redis, lock_key, lock_token, tokens
    ):
        yield token


def wrap_stream_status(
    timing: TurnTimingTracker | None,
    on_status: StreamStatusFn | None,
) -> StreamStatusFn | None:
    return _resources.wrap_stream_status(timing, on_status)


def weighted_reserve_tokens(
    *,
    content: str,
    model: str,
    settings: Settings,
    max_output: int | None = None,
    vision_extra: int = 0,
) -> int:
    return _resources.weighted_reserve_tokens(
        _seams(),
        content=content,
        model=model,
        settings=settings,
        max_output=max_output,
        vision_extra=vision_extra,
    )


def prompt_weighted_reserve_tokens(
    prompt_messages: list[dict[str, Any]],
    *,
    model: str,
    settings: Settings,
    max_output: int | None = None,
) -> int:
    return _resources.prompt_weighted_reserve_tokens(
        _seams(),
        prompt_messages,
        model=model,
        settings=settings,
        max_output=max_output,
    )


async def _top_up_reserve_for_prompt(
    res: TurnResources,
    *,
    settings: Settings,
    ctx: StreamContext,
    daily_limit: int,
) -> None:
    await _resources.top_up_reserve_for_prompt(
        _seams(),
        res,
        settings=settings,
        ctx=ctx,
        daily_limit=daily_limit,
    )


async def reserve_turn_quota(
    redis: Redis,
    *,
    user: User,
    content: str,
    model: str,
    settings: Settings,
    daily_limit: int | None = None,
    max_output: int | None = None,
    vision_extra: int = 0,
    seed: bool = True,
) -> int:
    return await _resources.reserve_turn_quota(
        _seams(),
        redis,
        user=user,
        content=content,
        model=model,
        settings=settings,
        daily_limit=daily_limit,
        max_output=max_output,
        vision_extra=vision_extra,
        seed=seed,
    )


async def _try_image_gen_for_turn(
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    result: dict[str, Any] | None,
    create_user_message: bool,
    replace_assistant_id: UUID | None = None,
) -> bool:
    return await _entry.try_image_gen_for_turn(
        _seams(),
        settings,
        user=user,
        chat_id=chat_id,
        content=content,
        result=result,
        create_user_message=create_user_message,
        replace_assistant_id=replace_assistant_id,
    )


async def stream_chat_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None = None,
    attachment_ids: list[UUID] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    user: User | None = None,
    skip_usage_seed: bool = False,
    resources: TurnResources | None = None,
) -> AsyncIterator[str]:
    async for token in _entry.stream_chat_response(
        _seams(),
        redis,
        settings,
        user_id=user_id,
        chat_id=chat_id,
        content=content,
        model_alias=model_alias,
        attachment_ids=attachment_ids,
        should_cancel=should_cancel,
        result=result,
        client_timezone=client_timezone,
        client_location=client_location,
        client_latitude=client_latitude,
        client_longitude=client_longitude,
        on_status=on_status,
        on_reasoning=on_reasoning,
        user=user,
        skip_usage_seed=skip_usage_seed,
        resources=resources,
    ):
        yield token


async def stream_regenerate_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
) -> AsyncIterator[str]:
    async for token in _entry.stream_regenerate_response(
        _seams(),
        redis,
        settings,
        user_id=user_id,
        chat_id=chat_id,
        model_alias=model_alias,
        should_cancel=should_cancel,
        result=result,
        client_timezone=client_timezone,
        client_location=client_location,
        client_latitude=client_latitude,
        client_longitude=client_longitude,
        on_status=on_status,
        on_reasoning=on_reasoning,
    ):
        yield token


async def stream_edit_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    message_id: UUID,
    new_content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
) -> AsyncIterator[str]:
    async for token in _entry.stream_edit_response(
        _seams(),
        redis,
        settings,
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        new_content=new_content,
        model_alias=model_alias,
        should_cancel=should_cancel,
        result=result,
        client_timezone=client_timezone,
        client_location=client_location,
        client_latitude=client_latitude,
        client_longitude=client_longitude,
        on_status=on_status,
        on_reasoning=on_reasoning,
    ):
        yield token


async def stream_and_finalize(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    result: dict[str, Any] | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    resources: TurnResources | None = None,
) -> AsyncIterator[str]:
    async for token in _pipeline.stream_and_finalize(
        _seams(),
        redis,
        settings,
        ctx,
        should_cancel=should_cancel,
        result=result,
        on_status=on_status,
        on_reasoning=on_reasoning,
        resources=resources,
    ):
        yield token


async def _run_tool_loop_path(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    usage: dict[str, int],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> None:
    """Compatibility wrapper for focused pipeline tests and callers."""
    await _pipeline.run_tool_loop_path(
        _seams(),
        redis,
        settings,
        ctx,
        usage=usage,
        on_status=on_status,
        should_cancel=should_cancel,
    )


__all__ = [
    "prompt_weighted_reserve_tokens",
    "reserve_turn_quota",
    "stream_and_finalize",
    "stream_chat_response",
    "stream_edit_response",
    "stream_regenerate_response",
    "weighted_reserve_tokens",
    "wrap_stream_status",
]
