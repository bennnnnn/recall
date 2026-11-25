"""OpenRouter text-to-speech HTTP calls (provider boundary): Listen's Kokoro voices.

``POST /api/v1/audio/speech`` is OpenAI's speech request with OpenRouter's ``provider``
routing (OpenRouter's API reference, "Create speech"): it answers with the audio bytes,
``audio/mpeg`` for ``mp3``, the format the phone plays from tts-1 too. It is billed by the
character read; the response's ``X-Generation-Id`` names the call in OpenRouter's log.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.log_text import log_safe
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
# A clip is about 150 characters (the phone's ``ttsLead.ts``): Kokoro answered one in about
# half a second (2026-11-24). Past this the request falls back to tts-1 inside the phone's
# own 60 s wait.
_TTS_TIMEOUT = 20.0
# DeepInfra serves Kokoro at $0.99 per 1M characters, Together at $4: ask DeepInfra first,
# and let OpenRouter fall back to Together when DeepInfra is down.
_PROVIDER = {"order": ["deepinfra"], "allow_fallbacks": True}


async def synthesize_via_openrouter(
    settings: Settings,
    text: str,
    *,
    model: str,
    voice: str,
) -> tuple[bytes, str] | None:
    """MP3 audio of ``text`` read by ``model`` in ``voice``; None on any failure."""
    payload: dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "provider": _PROVIDER,
    }
    try:
        response = await get_pooled_client(_TTS_TIMEOUT).post(
            _OPENROUTER_SPEECH_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            logger.warning(
                "OpenRouter TTS failed model=%s status=%s body=%s",
                log_safe(model),
                response.status_code,
                response.text[:500],
            )
            return None
        content_type = (response.headers.get("content-type") or "").split(";")[0].strip()
        if not response.content or not content_type.startswith("audio/"):
            logger.warning(
                "OpenRouter TTS returned no audio model=%s type=%s",
                log_safe(model),
                log_safe(content_type),
            )
            return None
        return response.content, content_type
    except Exception:
        logger.exception("OpenRouter TTS failed model=%s chars=%s", log_safe(model), len(text))
        return None
