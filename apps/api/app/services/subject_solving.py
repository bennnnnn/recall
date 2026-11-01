"""Neutral chat integration for independent deterministic subject solvers.

The registry lives here, with chat, so a subject package never decides which
peer owns a turn. Adapters call the solvers that already exist. They do not
reimplement extraction or presentation.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.readings import read_off_loop, reading
from app.modules.math.schemas import MathImageExtract
from app.modules.math.tools.prompt import (
    NOTHING_TO_GRAPH,
    build_math_augmentation,
)
from app.modules.physics.prompt import build_physics_augmentation
from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock, VerifiedSolveBlock
from app.services.which_subject import SubjectName as SubjectName
from app.services.which_subject import read_subject_reason


@dataclass(frozen=True)
class SubjectAugmentation:
    subject: SubjectName | None
    prompt_block: str | None
    verified: VerifiedSolveBlock | None
    unverified: bool = False
    # Both halves of "…, and also …" already rendered. Chat shows this and
    # does not ask the model to redo either half.
    direct_text: str | None = None


@dataclass(frozen=True)
class SubjectAdapter:
    """One subject's solve and direct-reply hooks. Detection order is separate."""

    name: SubjectName
    augment: Callable[..., Awaitable[SubjectAugmentation]]
    direct_reply: Callable[..., str | None]


def detect_subject(
    text: str,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
    chemistry_enabled: bool = True,
) -> SubjectName | None:
    """Pick one subject for this line.

    An image math extract is math. A closed chemistry extraction wins over physics and
    math: molarity and Gibbs notation look like algebra, and a mass percent has masses
    physics would read. Otherwise physics wins over math, and a chemistry question that
    chemistry could not close (a pH, a Ka, a molarity, a formula or an equation) is still
    chemistry's, never math's. Chemistry runs for a lookup only when neither peer has
    claimed the line.
    """
    if image_math_extract is not None:
        return "math"
    return _subject_of_text(text, has_image_attachment, chemistry_enabled)


async def read_subject(
    text: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
) -> SubjectName | None:
    """``detect_subject`` read off the event loop, in the SymPy pool (``core/readings``)."""
    if image_math_extract is not None:
        return "math"
    return await read_off_loop(
        _subject_of_text,
        text,
        has_image_attachment,
        settings.chemistry_enabled,
        timeout=settings.subject_read_timeout_seconds,
    )


@reading(declined=None)
def _subject_of_text(
    text: str, has_image_attachment: bool, chemistry_enabled: bool
) -> SubjectName | None:
    """``detect_subject`` for a line with no image extract: a reading (``core/readings``)."""
    found = read_subject_reason(text, has_image_attachment, chemistry_enabled)
    return None if found is None else found.subject


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
        # tells the model not to claim a check. The reply does not say it
        # could not be verified.
        unverified=solve_failed,
    )


def _direct_physics(
    verified: VerifiedSolveBlock,
    user_text: str,
    *,
    has_image_attachment: bool,
    verified_request_text: str | None,
) -> str | None:
    del verified_request_text
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
        # Asking which function to graph is not an unverified answer.
        unverified=block is not None and math_verified is None and block is not NOTHING_TO_GRAPH,
    )


def _direct_math(
    verified: VerifiedSolveBlock,
    user_text: str,
    *,
    has_image_attachment: bool,
    verified_request_text: str | None,
) -> str | None:
    if not isinstance(verified, VerifiedMathBlock):
        return None
    from app.modules.math.tools.direct import maybe_direct_math_reply

    return maybe_direct_math_reply(
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
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
    from app.modules.chemistry.reply_policy import attach_chemistry_fence_hint

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
    verified_request_text: str | None,
) -> str | None:
    del verified_request_text
    from app.modules.chemistry.block import VerifiedChemistry
    from app.modules.chemistry.direct import maybe_direct_chemistry_reply

    if not isinstance(verified, VerifiedChemistry):
        return None
    return maybe_direct_chemistry_reply(
        verified,
        has_image_attachment=has_image_attachment,
        user_text=user_text,
    )


# "Dilute …, and also solve …" is two problems. One failed reading of the
# whole line used to stamp "couldn't verify" under two correct answers.
_AND_ALSO = re.compile(r"(?:,\s*|\s+)\band\s+also\b\s+", re.IGNORECASE)


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
    pair: bool = True,
) -> SubjectAugmentation:
    if pair and not has_image_attachment:
        paired = await _paired_direct_reply(
            user_content,
            settings,
            redis=redis,
        )
        if paired is not None:
            return SubjectAugmentation(None, None, None, direct_text=paired)
    math_text = math_user_content or user_content
    subject = detected_subject or await read_subject(
        user_content,
        settings,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
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


async def _paired_direct_reply(
    user_content: str,
    settings: Settings,
    *,
    redis: Redis | None,
) -> str | None:
    parts = [part.strip().rstrip(".").strip() for part in _AND_ALSO.split(user_content)]
    parts = [part for part in parts if part]
    if len(parts) != 2:
        return None
    replies: list[str] = []
    for part in parts:
        piece = await build_subject_augmentation(part, settings, pair=False, redis=redis)
        reply = await read_direct_reply(piece.verified, part, settings)
        if reply is None:
            return None
        replies.append(reply.strip())
    # Each question worked and answered on its own, a hairline between them.
    return "\n\n---\n\n".join(replies)


async def read_direct_reply(
    verified: VerifiedSolveBlock | None,
    user_text: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
    verified_request_text: str | None = None,
) -> str | None:
    """``maybe_direct_subject_reply`` off the event loop: its checks parse with SymPy."""
    if verified is None:
        return None
    return await read_off_loop(
        maybe_direct_subject_reply,
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
        verified_request_text=verified_request_text,
        timeout=settings.stem_solve_timeout_seconds,
    )


def maybe_direct_subject_reply(
    verified: VerifiedSolveBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
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
        verified_request_text=verified_request_text,
    )
