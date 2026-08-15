"""Extract an equation from an image via vision-chat (best-effort)."""

from __future__ import annotations

import base64
import json
import logging

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.math_schemas import MathImageExtract

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = (
    "Extract the primary math problem from this image as a single JSON object "
    "(not an array). Always include found (boolean) and variables (array). "
    "Use ASCII math (* / ** for multiply/divide/power). Never invent dimensions "
    "or freehand diagrams — only extract numbers/expressions printed on the page. "
    "kind is one of: equation, system, inequality, calculus, limit, graph, "
    "rectangle, circle, triangle_sides, statistics. "
    "Equation: fill lhs, rhs. "
    'Example: {"kind":"equation","lhs":"2*x+3","rhs":"7","variables":["x"],'
    '"found":true}. '
    "System: also fill equations as [lhs,rhs] pairs for EVERY equation "
    "(including the first) and set lhs/rhs to the first pair. "
    'Example: {"kind":"system","lhs":"x+y","rhs":"5",'
    '"equations":[["x+y","5"],["x-y","1"]],"variables":["x","y"],"found":true}. '
    'Inequality: comparator one of "<", ">", "<=", ">=". '
    'Example: {"kind":"inequality","lhs":"x**2-1","rhs":"0","comparator":">",'
    '"variables":["x"],"found":true}. '
    "Calculus: fill expr plus operation "
    "(simplify|differentiate|integrate|factor|expand). For a definite integral "
    "also fill integral_lower and integral_upper (both required; omit both "
    "for indefinite). "
    'Example: {"kind":"calculus","operation":"differentiate","expr":"x**2",'
    '"variables":["x"],"found":true}. '
    'Definite: {"kind":"calculus","operation":"integrate","expr":"x**2",'
    '"integral_lower":"0","integral_upper":"1","variables":["x"],"found":true}. '
    "Limit: fill expr and limit_point (number or infinity). "
    'Example: {"kind":"limit","expr":"sin(x)/x","limit_point":"0",'
    '"variables":["x"],"found":true}. '
    "Graph: fill expr to plot as y=f(x). "
    'Example: {"kind":"graph","expr":"x**2","variables":["x"],"found":true}. '
    "Rectangle/circle: fill printed width+height or radius and optional unit. "
    'Example: {"kind":"rectangle","width":8,"height":5,"unit":"cm","found":true}. '
    "Triangle with three printed side lengths (SSS): fill tri_a, tri_b, tri_c. "
    'Example: {"kind":"triangle_sides","tri_a":3,"tri_b":4,"tri_c":5,'
    '"unit":"cm","found":true}. '
    "Statistics on a printed data list: fill stats_numbers and stats_op "
    "(mean|median|mode|variance|stdev). "
    'Example: {"kind":"statistics","stats_op":"mean","stats_numbers":[1,3,5,7],'
    '"found":true}. '
    'If nothing extractable, set found=false and use lhs/rhs of "0".'
)

# Must stay byte-for-byte identical to MATH_CAMERA_PROMPT in
# apps/mobile/lib/attachments.ts — this is an exact-match trigger phrase
# (is_math_camera_prompt below), not user-facing copy, so it doesn't go
# through i18n. If either side's wording changes without the other, the
# verified-math augmentation silently stops firing for the camera flow.
MATH_CAMERA_PROMPT = "Solve the math problem in this image step by step."

_SOLVE_KINDS = frozenset({"equation", "system", "inequality"})


def is_math_camera_prompt(text: str) -> bool:
    return text.strip().casefold() == MATH_CAMERA_PROMPT.casefold()


def camera_math_user_suffix(extracted: MathImageExtract) -> str | None:
    """Extra user-text for the model. Structured kinds must not inject
    ``Solve: 0 = 0`` from unused lhs/rhs defaults."""
    if not extracted.found:
        return None
    if extracted.kind not in _SOLVE_KINDS:
        return None
    if extracted.kind == "inequality":
        cmp_op = extracted.comparator if extracted.comparator else "="
        return f"Solve: {extracted.lhs} {cmp_op} {extracted.rhs}"
    if extracted.kind == "system" and extracted.equations:
        lines = "\n".join(f"{lhs} = {rhs}" for lhs, rhs in extracted.equations)
        return f"Solve:\n{lines}"
    return f"Solve: {extracted.lhs} = {extracted.rhs}"


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
        response = await litellm_gateway.vision_completion(
            settings=settings,
            model_alias="vision-chat",
            messages=messages,
            max_tokens=384,
            response_format={"type": "json_object"},
            timeout_seconds=settings.math_image_extract_timeout_seconds,
        )
        if response is None:
            return None
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
