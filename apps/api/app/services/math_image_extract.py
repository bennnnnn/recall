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
    "Extract the primary math problem from this image as a single JSON object "
    "(not an array) with keys: "
    'kind ("equation", "system", or "inequality"), '
    "lhs, rhs (the first or only equation/inequality side — always fill these, "
    "even for a system), "
    "variables (array of variable names), "
    'equations (ONLY when kind is "system": array of [lhs, rhs] pairs for EVERY '
    "equation in the system, including the first), "
    'comparator (ONLY when kind is "inequality": one of "<", ">", "<=", ">="), '
    "and found (boolean). "
    'Single equation: {"kind":"equation","lhs":"2*x+3","rhs":"7","variables":["x"],'
    '"found":true}. '
    'System of equations: {"kind":"system","lhs":"x+y","rhs":"5",'
    '"equations":[["x+y","5"],["x-y","1"]],"variables":["x","y"],"found":true}. '
    'Inequality: {"kind":"inequality","lhs":"x**2-1","rhs":"0","comparator":">",'
    '"variables":["x"],"found":true}. '
    'If no equation is visible, set found=false and use lhs/rhs of "0".'
)

# Must stay byte-for-byte identical to MATH_CAMERA_PROMPT in
# apps/mobile/lib/attachments.ts — this is an exact-match trigger phrase
# (is_math_camera_prompt below), not user-facing copy, so it doesn't go
# through i18n. If either side's wording changes without the other, the
# verified-math augmentation silently stops firing for the camera flow.
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
        async with asyncio.timeout(settings.math_image_extract_timeout_seconds):
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
        # Vision models sometimes wrap the object in a one-element array.
        if isinstance(data_obj, list):
            if len(data_obj) != 1 or not isinstance(data_obj[0], dict):
                return None
            data_obj = data_obj[0]
        parsed = MathImageExtract.model_validate(data_obj)
        if not parsed.found:
            return None
        return parsed
    except Exception:
        # Was logger.debug — silently swallowed a real OCR outage (bad
        # vision-model response, network failure, timeout) with no signal
        # in prod logs at the default level.
        logger.warning("math image extract failed", exc_info=True)
        return None
