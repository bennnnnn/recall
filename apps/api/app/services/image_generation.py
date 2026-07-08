"""Text-to-image via OpenRouter Image API."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Literal

import httpx

from app.core.config import Settings
from app.gateways import mock_llm

logger = logging.getLogger(__name__)

_MAX_PROMPT_LEN = 2000
_OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
_GENERATE_TIMEOUT = 120.0

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

    model = (settings.image_generation_model or "black-forest-labs/flux-schnell").strip()
    payload: dict[str, object] = {
        "model": model,
        "prompt": cleaned,
        "n": 1,
        "output_format": "png",
    }
    normalized_ratio = normalize_aspect_ratio(aspect_ratio)
    if normalized_ratio:
        payload["aspect_ratio"] = normalized_ratio

    try:
        async with httpx.AsyncClient(timeout=_GENERATE_TIMEOUT) as client:
            response = await client.post(
                _OPENROUTER_IMAGES_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if response.status_code >= 400:
                logger.warning(
                    "OpenRouter image generation failed model=%s status=%s body=%s",
                    model,
                    response.status_code,
                    response.text[:500],
                )
            response.raise_for_status()
            data = response.json()
        items = data.get("data")
        if not isinstance(items, list) or not items:
            logger.warning("OpenRouter image generation returned no data model=%s", model)
            return None
        first = items[0]
        if not isinstance(first, dict):
            return None
        b64_json = first.get("b64_json")
        if isinstance(b64_json, str) and b64_json.strip():
            try:
                raw = base64.b64decode(b64_json, validate=True)
            except (ValueError, binascii.Error):
                logger.warning("OpenRouter image generation returned invalid b64_json")
                return None
            if raw:
                return raw, "image/png"
        url = first.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=_GENERATE_TIMEOUT) as client:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                content_type = img_resp.headers.get("content-type", "image/png").split(";")[0]
                if img_resp.content:
                    return img_resp.content, content_type or "image/png"
        logger.warning("OpenRouter image generation response missing image payload model=%s", model)
        return None
    except Exception:
        logger.exception("Image generation failed model=%s prompt_len=%s", model, len(cleaned))
        return None
