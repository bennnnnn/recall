"""Neutral chat integration for independent deterministic subject solvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.models.schemas.math import MathImageExtract
from app.modules.math.tools.prompt import build_math_augmentation, needs_symbolic_math
from app.modules.physics.extract import needs_physics
from app.modules.physics.prompt import build_physics_augmentation
from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock, VerifiedSolveBlock

SubjectName = Literal["math", "physics"]


@dataclass(frozen=True)
class SubjectAugmentation:
    subject: SubjectName | None
    prompt_block: str | None
    verified: VerifiedSolveBlock | None
    unverified: bool = False


def detect_subject(
    text: str,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
) -> SubjectName | None:
    """Choose one peer subject before extraction; physics never enters math."""
    if image_math_extract is not None:
        return "math"
    if needs_physics(text):
        return "physics"
    if needs_symbolic_math(text, has_image_attachment=has_image_attachment):
        return "math"
    return None


async def build_subject_augmentation(
    user_content: str,
    settings: Settings,
    *,
    math_user_content: str | None = None,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
    prior_user_messages: list[str] | None = None,
    response_intent_text: str | None = None,
    detected_subject: SubjectName | None = None,
) -> SubjectAugmentation:
    math_text = math_user_content or user_content
    subject = detected_subject or detect_subject(
        user_content,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
    )
    if subject is None and math_user_content is not None:
        subject = "math"
    if subject == "physics":
        block, physics_verified = await build_physics_augmentation(
            user_content,
            settings,
            needs_subject=True,
        )
        return SubjectAugmentation(
            subject="physics",
            prompt_block=block,
            verified=physics_verified,
            unverified=block is not None and physics_verified is None,
        )
    if subject == "math":
        block, math_verified = await build_math_augmentation(
            math_text,
            settings,
            has_image_attachment=has_image_attachment,
            image_math_extract=image_math_extract,
            needs_math=True,
            prior_user_messages=prior_user_messages,
            response_intent_text=response_intent_text,
        )
        return SubjectAugmentation(
            subject="math",
            prompt_block=block,
            verified=math_verified,
            unverified=block is not None and math_verified is None,
        )
    return SubjectAugmentation(None, None, None)


def maybe_direct_subject_reply(
    verified: VerifiedSolveBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
    response_style: str = "balanced",
    verified_request_text: str | None = None,
) -> str | None:
    if isinstance(verified, VerifiedMathBlock):
        from app.modules.math.tools.direct import maybe_direct_math_reply

        return maybe_direct_math_reply(
            verified,
            user_text,
            has_image_attachment=has_image_attachment,
            response_style=response_style,
            verified_request_text=verified_request_text,
        )
    if isinstance(verified, VerifiedPhysicsBlock):
        from app.modules.physics.direct import maybe_direct_physics_reply

        return maybe_direct_physics_reply(
            verified,
            user_text,
            has_image_attachment=has_image_attachment,
        )
    return None
