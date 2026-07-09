"""Extract an equation from an image via vision-chat (best-effort)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging

from litellm import acompletion

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.math_schemas import MathImageExtract

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = (
    "Extract the primary math equation from this image as JSON with keys "
    "lhs, rhs, variables (array of variable names), and found (boolean). "
    'Example: {"lhs":"2*x+3","rhs":"7","variables":["x"],"found":true}. '
    'If no equation is visible, set found=false and use lhs/rhs of "0".'
)

MATH_CAMERA_PROMPT = "Solve the math problem in this image step by step."


def is_math_camera_prompt(text: str) -> bool:
    return text.strip().casefold() == MATH_CAMERA_PROMPT.casefold()


async def extract_equation_from_image(
    settings: Settings,
    *,
    content_type: str,
    data: bytes,
) -> MathImageExtract | None:
    """Best-effort vision extract — never raises into the chat path."""
    if not data:
        return None
    if mock_llm.should_mock_llm(settings):
        return MathImageExtract(lhs="2*x+3", rhs="7", variables=["x"], found=True)

    try:
        route = litellm_gateway.resolve_route("vision-chat")
        kwargs = litellm_gateway._litellm_kwargs(settings, route)
        mime = content_type.split(";")[0].strip() or "image/jpeg"
        encoded = base64.standard_b64encode(data).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _EXTRACT_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    },
                ],
            }
        ]
        async with asyncio.timeout(settings.math_solve_timeout_seconds):
            response = await acompletion(
                model=route.model,
                messages=messages,
                max_tokens=256,
                response_format={"type": "json_object"},
                **kwargs,
            )
        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data_obj = json.loads(raw.strip())
        parsed = MathImageExtract.model_validate(data_obj)
        if not parsed.found:
            return None
        return parsed
    except Exception:
        logger.debug("math image extract failed", exc_info=True)
        return None
