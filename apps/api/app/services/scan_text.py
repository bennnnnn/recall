"""Read a photographed problem back as plain text, with a subject's prompt.

This is not the math scanner: it does not call Mathpix and it asks for no
equation kinds. Chemistry and physics confirm the text with the student, and
the chat then solves that text like a typed question.
"""

from __future__ import annotations

import base64
import json
import logging

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm

logger = logging.getLogger(__name__)

MAX_READING = 2000
_MATH_KINDS = frozenset({"equation", "system", "inequality"})


def reading_from_vision(raw: str) -> str:
    """Plain problem text. A math-kind JSON object is not a reading."""
    text = raw.strip()
    if text.startswith("```"):
        fence = text.split("```", 2)
        text = fence[1] if len(fence) > 1 else ""
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            kind = data.get("kind")
            if "lhs" in data or (isinstance(kind, str) and kind in _MATH_KINDS):
                return ""
            for key in ("problem", "text", "reading"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
            else:
                return ""
    if len(text) > MAX_READING:
        text = text[:MAX_READING].rstrip()
    return text


async def read_problem_text(
    settings: Settings,
    *,
    prompt: str,
    content_type: str,
    data: bytes,
    mock_reading: str,
) -> str:
    """The written problem, or empty when the page cannot be read."""
    if not data:
        return ""
    if mock_llm.should_mock_llm(settings):
        return mock_reading
    try:
        mime = content_type.split(";")[0].strip() or "image/jpeg"
        encoded = base64.standard_b64encode(data).decode("ascii")
        response = await litellm_gateway.vision_completion(
            settings=settings,
            model_alias="vision-chat",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{encoded}"},
                        },
                    ],
                }
            ],
            max_tokens=512,
            timeout_seconds=settings.math_image_extract_timeout_seconds,
        )
    except Exception:
        logger.warning("scan text read failed", exc_info=True)
        return ""
    if response is None:
        return ""
    try:
        raw = response.choices[0].message.content or ""
    except Exception:
        logger.warning("scan text read had no text", exc_info=True)
        return ""
    return reading_from_vision(raw)
