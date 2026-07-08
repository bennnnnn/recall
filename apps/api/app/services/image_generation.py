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
_GENERATE_TIMEOUT = 90.0

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
_ALLOWED_ASPECT_RATIOS: frozenset[str] = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4"})
_DEFAULT_FALLBACK_MODELS = (
    "bytedance-seed/seedream-4.5",
    "black-forest-labs/flux.2-pro",
)


def normalize_aspect_ratio(value: str | None) -> AspectRatio | None:
    if not value:
        return None
    trimmed = value.strip()
    if trimmed in _ALLOWED_ASPECT_RATIOS:
        return trimmed  # type: ignore[return-value]
    return None


def image_model_candidates(settings: Settings) -> list[str]:
    """Primary model first, then configured fallbacks (deduped)."""
    primary = (settings.image_generation_model or "google/gemini-2.5-flash-image").strip()
    extra = [
        part.strip()
        for part in settings.image_generation_fallback_models.split(",")
        if part.strip()
    ]
    if not extra:
        extra = list(_DEFAULT_FALLBACK_MODELS)
    seen: set[str] = set()
    ordered: list[str] = []
    for model in [primary, *extra]:
        if model and model not in seen:
            seen.add(model)
            ordered.append(model)
    return ordered


def _decode_image_payload(first: dict[str, object]) -> tuple[bytes, str] | None:
    b64_json = first.get("b64_json")
    if isinstance(b64_json, str) and b64_json.strip():
        try:
            raw = base64.b64decode(b64_json, validate=True)
        except (ValueError, binascii.Error):
            logger.warning("OpenRouter image generation returned invalid b64_json")
            return None
        if raw:
            media_type = first.get("media_type")
            content_type = (
                media_type.split(";", 1)[0].strip()
                if isinstance(media_type, str) and media_type.strip()
                else "image/png"
            )
            return raw, content_type

    url = first.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return None  # caller may fetch URL in a follow-up request
    return None


async def _fetch_image_url(url: str) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=_GENERATE_TIMEOUT) as client:
            img_resp = await client.get(url)
            if img_resp.status_code >= 400:
                logger.warning(
                    "OpenRouter image URL fetch failed status=%s url=%s",
                    img_resp.status_code,
                    url[:120],
                )
                return None
            content_type = img_resp.headers.get("content-type", "image/png").split(";")[0]
            if img_resp.content:
                return img_resp.content, content_type or "image/png"
    except Exception:
        logger.exception("OpenRouter image URL fetch failed url=%s", url[:120])
    return None


async def _generate_with_model(
    settings: Settings,
    *,
    model: str,
    prompt: str,
    aspect_ratio: str | None,
) -> tuple[bytes, str] | None:
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "output_format": "png",
    }
    normalized_ratio = normalize_aspect_ratio(aspect_ratio)
    if normalized_ratio:
        payload["aspect_ratio"] = normalized_ratio

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
            return None
        data = response.json()

    items = data.get("data")
    if not isinstance(items, list) or not items:
        logger.warning("OpenRouter image generation returned no data model=%s", model)
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None

    decoded = _decode_image_payload(first)
    if decoded:
        return decoded

    url = first.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return await _fetch_image_url(url)

    logger.warning("OpenRouter image generation response missing image payload model=%s", model)
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

    last_error: str | None = None
    for model in image_model_candidates(settings):
        try:
            generated = await _generate_with_model(
                settings,
                model=model,
                prompt=cleaned,
                aspect_ratio=aspect_ratio,
            )
            if generated:
                if model != image_model_candidates(settings)[0]:
                    logger.info(
                        "Image generation succeeded with fallback model=%s prompt_len=%s",
                        model,
                        len(cleaned),
                    )
                return generated
            last_error = f"no image payload from {model}"
        except Exception:
            logger.exception("Image generation failed model=%s prompt_len=%s", model, len(cleaned))
            last_error = f"exception from {model}"

    if last_error:
        logger.warning(
            "Image generation exhausted models prompt_len=%s last=%s",
            len(cleaned),
            last_error,
        )
    return None
