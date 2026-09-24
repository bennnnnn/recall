"""Pre-stream symbolic math augmentation for chat prompts."""

from __future__ import annotations

from app.modules.math import solve as math_solve
from app.modules.math.tools.block import (
    VerifiedMathBlock,
    _answer_canonical,
    _build_verified_block,
    _diagram_block,
    _finish_with_answer,
    _format_equation_answer,
    _format_system_answer,
)
from app.modules.math.tools.direct import (
    can_direct_verified_math_reply,
    format_direct_math_reply,
    maybe_direct_math_reply,
    wants_math_explanation,
)
from app.modules.math.tools.extract import extract_math_intent
from app.modules.math.tools.prompt import (
    _build_verified_block_async,
    _intent_from_image_extract,
    augment_prompt_messages,
    build_math_augmentation,
    needs_symbolic_math,
)

__all__ = [
    "VerifiedMathBlock",
    "_answer_canonical",
    "_build_verified_block",
    "_build_verified_block_async",
    "_diagram_block",
    "_finish_with_answer",
    "_format_equation_answer",
    "_format_system_answer",
    "_intent_from_image_extract",
    "augment_prompt_messages",
    "build_math_augmentation",
    "can_direct_verified_math_reply",
    "extract_math_intent",
    "format_direct_math_reply",
    "math_solve",
    "maybe_direct_math_reply",
    "needs_symbolic_math",
    "wants_math_explanation",
]
