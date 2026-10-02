"""Read a photographed chemistry problem back as plain text.

This is not the math scanner. It does not call Mathpix and it does not ask
for equation, system, or inequality kinds. The student confirms the text,
then the chat solves that text alone.
"""

from __future__ import annotations

import base64
import json
import logging

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm

logger = logging.getLogger(__name__)

CHEMISTRY_READ_PROMPT = (
    "Read the chemistry problem written in this image. "
    "Return only that problem as plain text. "
    "Do not solve it. Do not describe glassware, apparatus, or a structure. "
    "If there is no written problem, return nothing."
)

_MAX_READING = 2000
_MATH_KINDS = frozenset({"equation", "system", "inequality"})
_MOCK_READING = "Find the molar mass of H2O"


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
    if len(text) > _MAX_READING:
        text = text[:_MAX_READING].rstrip()
    return text


async def read_chemistry_problem(
    settings: Settings,
    *,
    content_type: str,
    data: bytes,
) -> str:
    """The written problem, or empty when the page cannot be read."""
    if not data:
        return ""
    if mock_llm.should_mock_llm(settings):
        return _MOCK_READING
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
                        {"type": "text", "text": CHEMISTRY_READ_PROMPT},
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
        logger.warning("chemistry scan read failed", exc_info=True)
        return ""
    if response is None:
        return ""
    try:
        raw = response.choices[0].message.content or ""
    except Exception:
        logger.warning("chemistry scan read had no text", exc_info=True)
        return ""
    return reading_from_vision(raw)
