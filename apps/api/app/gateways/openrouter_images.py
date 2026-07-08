"""OpenRouter dedicated Image API (`POST /api/v1/images`)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
_OPENROUTER_IMAGE_MODELS_URL = "https://openrouter.ai/api/v1/images/models"
_HTTP_REFERER = "https://github.com/bennnnnn/recall"
_APP_TITLE = "Recall"


def openrouter_image_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": _HTTP_REFERER,
        "X-Title": _APP_TITLE,
    }


def configured_provider_order(settings: Settings) -> list[str]:
    return [
        part.strip() for part in settings.image_generation_provider_order.split(",") if part.strip()
    ]


async def list_provider_slugs(settings: Settings, model: str) -> list[str]:
    """Provider slugs for a model (from OpenRouter endpoints API)."""
    url = f"{_OPENROUTER_IMAGE_MODELS_URL}/{model}/endpoints"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=openrouter_image_headers(settings))
            if response.status_code >= 400:
                logger.warning(
                    "OpenRouter image endpoints lookup failed model=%s status=%s",
                    model,
                    response.status_code,
                )
                return []
            data = response.json()
    except Exception:
        logger.exception("OpenRouter image endpoints lookup failed model=%s", model)
        return []

    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list):
        return []
    slugs: list[str] = []
    seen: set[str] = set()
    for item in endpoints:
        if not isinstance(item, dict):
            continue
        slug = item.get("provider_slug")
        if isinstance(slug, str) and slug.strip() and slug not in seen:
            seen.add(slug)
            slugs.append(slug)
    return slugs


def provider_attempts(
    settings: Settings, *, model: str, endpoint_slugs: list[str]
) -> list[dict[str, Any] | None]:
    """Routing attempts: workspace default first, then explicit provider pins.

    Workspace routing (https://openrouter.ai/workspaces/.../routing) applies to the
    API key on the first attempt. When that fails, we pin `provider.order` per slug —
    the same fields chat completions use, supported by the Image API in practice.
    """
    configured = configured_provider_order(settings)
    if configured:
        return [
            {
                "order": configured,
                "allow_fallbacks": settings.image_generation_allow_provider_fallbacks,
            }
        ]

    attempts: list[dict[str, Any] | None] = [None]
    preferred = _PREFERRED_PROVIDER_ORDER.get(model, [])
    ordered_slugs: list[str] = []
    seen: set[str] = set()
    for slug in [*preferred, *endpoint_slugs]:
        if slug and slug not in seen:
            seen.add(slug)
            ordered_slugs.append(slug)
    for slug in ordered_slugs:
        attempts.append(
            {
                "order": [slug],
                "allow_fallbacks": settings.image_generation_allow_provider_fallbacks,
            }
        )
    return attempts


# Vertex is often more reliable than Google AI Studio for Gemini image models.
_PREFERRED_PROVIDER_ORDER: dict[str, list[str]] = {
    "google/gemini-2.5-flash-image": ["google-vertex", "google-ai-studio"],
    "google/gemini-3.1-flash-image": ["google-vertex", "google-ai-studio"],
    "google/gemini-3-pro-image": ["google-vertex", "google-ai-studio"],
}
