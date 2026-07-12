"""OpenRouter text-to-image HTTP calls (provider boundary)."""

from __future__ import annotations

import base64
import binascii
import logging

import httpx

from app.core.config import Settings
from app.gateways import safe_fetch
from app.services.attachment_content import MAX_ATTACHMENT_SIZE

logger = logging.getLogger(__name__)

_OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
_GENERATE_TIMEOUT = 120.0


async def generate_via_openrouter(
    settings: Settings,
    *,
    prompt: str,
    model: str,
    aspect_ratio: str | None = None,
) -> tuple[bytes, str] | None:
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "output_format": "png",
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio

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
                # BUG FIX: every other attachment path (routers/attachments.py)
                # enforces MAX_ATTACHMENT_SIZE on both presign and the actual
                # bytes. Generated images skipped that cap entirely — an
                # oversized provider response would get written straight to
                # storage/DB with no guard.
                if len(raw) > MAX_ATTACHMENT_SIZE:
                    logger.warning(
                        "OpenRouter image generation b64_json exceeds size cap model=%s bytes=%s",
                        model,
                        len(raw),
                    )
                    return None
                return raw, "image/png"
        url = first.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            async with httpx.AsyncClient(
                timeout=_GENERATE_TIMEOUT, follow_redirects=False
            ) as client:
                img_resp = await safe_fetch.fetch_safely(client, url)
                img_resp.raise_for_status()
                content_type = (
                    img_resp.headers.get("content-type", "image/png").split(";")[0].strip().lower()
                )
                if img_resp.content:
                    if len(img_resp.content) > MAX_ATTACHMENT_SIZE:
                        logger.warning(
                            "OpenRouter image generation URL response exceeds size cap "
                            "model=%s bytes=%s",
                            model,
                            len(img_resp.content),
                        )
                        return None
                    return img_resp.content, content_type or "image/png"
        logger.warning("OpenRouter image generation response missing image payload model=%s", model)
        return None
    except Exception:
        logger.exception("Image generation failed model=%s prompt_len=%s", model, len(prompt))
        return None
