"""Pre-stream symbolic math augmentation for chat prompts."""

from __future__ import annotations

from app.services import math_service
from app.services.math_tools.block import (
    VerifiedMathBlock,
    _answer_canonical,
    _build_verified_block,
    _diagram_block,
    _fence,
    _finish_with_answer,
    _format_equation_answer,
    _format_system_answer,
)
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.prompt import (
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
    "_fence",
    "_finish_with_answer",
    "_format_equation_answer",
    "_format_system_answer",
    "_intent_from_image_extract",
    "augment_prompt_messages",
    "build_math_augmentation",
    "extract_math_intent",
    "math_service",
    "needs_symbolic_math",
]
