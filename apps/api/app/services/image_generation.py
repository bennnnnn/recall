"""Text-to-image product service (validation + mock; HTTP in gateways)."""

from __future__ import annotations

import logging
from typing import Literal

from app.core.config import Settings
from app.gateways import image_gateway, mock_llm

logger = logging.getLogger(__name__)

_MAX_PROMPT_LEN = 2000

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
_ALLOWED_ASPECT_RATIOS: frozenset[str] = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4"})


def normalize_aspect_ratio(value: str | None) -> AspectRatio | None:
    if not value:
        return None
    trimmed = value.strip()
    if trimmed in _ALLOWED_ASPECT_RATIOS:
        return trimmed  # type: ignore[return-value]
    return None


async def generate_image(
    settings: Settings,
    *,
    prompt: str,
    aspect_ratio: str | None = None,
) -> tuple[bytes, str] | None:
    """Return (image_bytes, content_type) or None on failure."""
    if not settings.image_generation_enabled:
        return None
    cleaned = prompt.strip()
    if not cleaned or len(cleaned) > _MAX_PROMPT_LEN:
        logger.warning("Image generation rejected: prompt length=%s", len(cleaned))
        return None
    if mock_llm.should_mock_llm(settings):
        return mock_llm.mock_image_bytes(), "image/png"
    if not settings.openrouter_api_key:
        return None

    model = (settings.image_generation_model or "black-forest-labs/flux.2-klein-4b").strip()
    return await image_gateway.generate_via_openrouter(
        settings,
        prompt=cleaned,
        model=model,
        aspect_ratio=normalize_aspect_ratio(aspect_ratio),
    )
