"""Test helper: run the web-search augmentation and splice its block into the messages.

Production builds the block with ``build_search_augmentation`` and injects it itself; tests use
this to see the prompt a turn would send.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.modules.web_search import augment
from app.services.prompt_inject import inject_before_last_user

if TYPE_CHECKING:
    from app.modules.chat import StreamStatusFn


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
) -> tuple[list[dict[str, str]], list[WebSearchHit]]:
    block, hits = await augment.build_search_augmentation(
        user_content,
        settings,
        messages=messages,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
        on_status=on_status,
        user=user,
        redis=redis,
    )
    if block is None:
        return messages, []
    return inject_before_last_user(messages, block), hits
