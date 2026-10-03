"""Neutral chat integration for independent deterministic subject solvers.

The registry lives here, with chat, so a subject package never decides which
peer owns a turn. Adapters call the solvers that already exist. They do not
reimplement extraction or presentation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from redis.asyncio import Redis

from app.core.config import Settings
from app.models.schemas.math import MathImageExtract
from app.modules.math.tools.prompt import build_math_augmentation, needs_symbolic_math
from app.modules.physics.extract import needs_physics
from app.modules.physics.prompt import build_physics_augmentation
from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock, VerifiedSolveBlock

SubjectName = Literal["math", "physics", "chemistry"]


@dataclass(frozen=True)
class SubjectAugmentation:
    subject: SubjectName | None
    prompt_block: str | None
    verified: VerifiedSolveBlock | None
    unverified: bool = False


@dataclass(frozen=True)
class SubjectAdapter:
    """One subject's solve and direct-reply hooks. Detection order is separate."""

    name: SubjectName
    augment: Callable[..., Awaitable[SubjectAugmentation]]
    direct_reply: Callable[..., str | None]


def _closed_chemistry(text: str) -> bool:
    """A chemistry cue plus a complete extraction, before algebra can claim it."""
    from app.modules.chemistry.extract import extract_chemistry_intent
    from app.modules.chemistry.request import is_chemistry_question

    if not is_chemistry_question(text):
        return False
    return extract_chemistry_intent(text) is not None


def detect_subject(
    text: str,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
    chemistry_enabled: bool = True,
) -> SubjectName | None:
    """Pick one subject for this line.

    An image math extract is math. Otherwise physics wins over math. A closed
    chemistry extraction wins over math, because molarity and Gibbs notation
    look like algebra, and chemistry runs for a lookup only when neither peer
    has claimed the line.
    """
    if image_math_extract is not None:
        return "math"
    from app.services.subject_scan import scanner_camera_subject

    # A subject's camera caption says "solve", which the math work-request
    # parser would claim. It is a photo plus a caption, not a math problem.
    scanned = scanner_camera_subject(text)
    if scanned == "chemistry":
        return "chemistry" if chemistry_enabled else None
    if scanned == "physics":
        return "physics"
    if needs_physics(text):
        return "physics"
    if chemistry_enabled and _closed_chemistry(text):
        return "chemistry"
    if needs_symbolic_math(text, has_image_attachment=has_image_attachment):
        return "math"
    if not chemistry_enabled:
        return None
    from app.modules.chemistry.request import is_chemistry_question

    if is_chemistry_question(text):
        return "chemistry"
    return None


def _physics_request_text(user_content: str) -> str:
    """The problem a physics turn verifies.

    A scanned photo's caption is a protocol line. When the student confirmed
    what the scanner read, that reading is the problem; without one, the
    caption alone gets the unverified physics note.
    """
    from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject

    if scanner_camera_subject(user_content) != "physics":
        return user_content
    return confirmed_scan_reading(user_content) or user_content


async def _augment_physics(
    user_content: str,
    settings: Settings,
    *,
    math_user_content: str,
    has_image_attachment: bool,
    image_math_extract: MathImageExtract | None,
    prior_user_messages: list[str] | None,
    response_intent_text: str | None,
    redis: Redis | None,
) -> SubjectAugmentation:
    del (
        math_user_content,
        has_image_attachment,
        image_math_extract,
        prior_user_messages,
        response_intent_text,
        redis,
    )
    block, physics_verified, solve_failed = await build_physics_augmentation(
        _physics_request_text(user_content),
        settings,
        needs_subject=True,
    )
    return SubjectAugmentation(
        subject="physics",
        prompt_block=block,
        verified=physics_verified,
        # No matching template is not a failed check. The prompt note still
        # tells the model not to claim verification; the user does not see
        # "I couldn't automatically verify this result."
        unverified=solve_failed,
    )


def _direct_physics(
    verified: VerifiedSolveBlock,
    user_text: str,
    *,
    has_image_attachment: bool,
    response_style: str,
    verified_request_text: str | None,
) -> str | None:
    del response_style, verified_request_text
    if not isinstance(verified, VerifiedPhysicsBlock):
        return None
    from app.modules.physics.direct import maybe_direct_physics_reply

    return maybe_direct_physics_reply(
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
    )


async def _augment_math(
    user_content: str,
    settings: Settings,
    *,
    math_user_content: str,
    has_image_attachment: bool,
    image_math_extract: MathImageExtract | None,
    prior_user_messages: list[str] | None,
    response_intent_text: str | None,
    redis: Redis | None,
) -> SubjectAugmentation:
    del user_content, redis
    block, math_verified = await build_math_augmentation(
        math_user_content,
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


def _direct_math(
    verified: VerifiedSolveBlock,
    user_text: str,
    *,
    has_image_attachment: bool,
    response_style: str,
    verified_request_text: str | None,
) -> str | None:
    if not isinstance(verified, VerifiedMathBlock):
        return None
    from app.modules.math.tools.direct import maybe_direct_math_reply

    return maybe_direct_math_reply(
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
        response_style=response_style,
        verified_request_text=verified_request_text,
    )


async def _augment_chemistry(
    user_content: str,
    settings: Settings,
    *,
    math_user_content: str,
    has_image_attachment: bool,
    image_math_extract: MathImageExtract | None,
    prior_user_messages: list[str] | None,
    response_intent_text: str | None,
    redis: Redis | None,
) -> SubjectAugmentation:
    del (
        math_user_content,
        has_image_attachment,
        image_math_extract,
        prior_user_messages,
        response_intent_text,
    )
    if not settings.chemistry_enabled:
        return SubjectAugmentation(None, None, None)
    from app.modules.chemistry.context import build_chemistry_augmentation
    from app.modules.chemistry.reading import chemistry_text_for_solve
    from app.services.chat.prompt_constants.visuals import attach_chemistry_fence_hint

    block, verified, declined = await build_chemistry_augmentation(
        chemistry_text_for_solve(user_content), settings, redis=redis
    )
    if block:
        block = attach_chemistry_fence_hint(block)
    return SubjectAugmentation(
        subject="chemistry" if block or verified else None,
        prompt_block=block,
        verified=verified,
        unverified=declined,
    )


def _direct_chemistry(
    verified: VerifiedSolveBlock,
    user_text: str,
    *,
    has_image_attachment: bool,
    response_style: str,
    verified_request_text: str | None,
) -> str | None:
    del response_style, verified_request_text
    from app.modules.chemistry.block import VerifiedChemistry
    from app.modules.chemistry.direct import maybe_direct_chemistry_reply

    if not isinstance(verified, VerifiedChemistry):
        return None
    return maybe_direct_chemistry_reply(
        verified,
        has_image_attachment=has_image_attachment,
        user_text=user_text,
    )


# Dispatch table. Detection order is ``detect_subject``, not this dict's order:
# physics still beats math, and a closed chemistry extraction beats algebra.
SUBJECT_ADAPTERS: dict[SubjectName, SubjectAdapter] = {
    "physics": SubjectAdapter("physics", _augment_physics, _direct_physics),
    "math": SubjectAdapter("math", _augment_math, _direct_math),
    "chemistry": SubjectAdapter("chemistry", _augment_chemistry, _direct_chemistry),
}


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
    redis: Redis | None = None,
) -> SubjectAugmentation:
    math_text = math_user_content or user_content
    subject = detected_subject or detect_subject(
        user_content,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
        chemistry_enabled=settings.chemistry_enabled,
    )
    adapter = SUBJECT_ADAPTERS.get(subject) if subject is not None else None
    if adapter is None:
        return SubjectAugmentation(None, None, None)
    return await adapter.augment(
        user_content,
        settings,
        math_user_content=math_text,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
        prior_user_messages=prior_user_messages,
        response_intent_text=response_intent_text,
        redis=redis,
    )


def maybe_direct_subject_reply(
    verified: VerifiedSolveBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
    response_style: str = "balanced",
    verified_request_text: str | None = None,
) -> str | None:
    if verified is None:
        return None
    adapter = SUBJECT_ADAPTERS.get(verified.subject)
    if adapter is None:
        return None
    return adapter.direct_reply(
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
        response_style=response_style,
        verified_request_text=verified_request_text,
    )
