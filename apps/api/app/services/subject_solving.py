"""Neutral chat integration for independent deterministic subject solvers.

The registry lives here, with chat, so a subject package never decides which
peer owns a turn. Adapters call the solvers that already exist. They do not
reimplement extraction or presentation.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.readings import read_off_loop, reading
from app.modules.math.schemas import MathImageExtract
from app.modules.math.tools.prompt import (
    NOTHING_TO_GRAPH,
    build_math_augmentation,
    needs_symbolic_math,
)
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.modules.physics.prompt import build_physics_augmentation
from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock, VerifiedSolveBlock

SubjectName = Literal["math", "physics", "chemistry"]


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


def _closed_chemistry(text: str) -> bool:
    """A chemistry cue plus a complete extraction, before algebra can claim it."""
    from app.modules.chemistry.extract import extract_chemistry_intent
    from app.modules.chemistry.request import is_chemistry_question

    if not is_chemistry_question(text):
        return False
    return extract_chemistry_intent(text) is not None


# What makes a chemistry question chemistry's even when no chemistry reader closes it: a
# symbol whose case is its meaning (pH, Ka), an amount in a chemistry unit (0.10 M, 3.0 mol,
# 98 g/mol), or a compound's formula (CH3COOH, NaCl). Maths read "Ka = 1.8 x 10^-5" as an
# equation in an unknown x and "verified" x = 55555.6; the question is chemistry's even when
# chemistry can only leave it to the model.
_CHEMISTRY_SYMBOL = re.compile(
    r"(?<![A-Za-z0-9])(?:pH|pOH|pKa|pKb|Ka|Kb|Kw|Ksp|Kc|Kp|Qc)(?![A-Za-z])"
)
_CHEMISTRY_AMOUNT = re.compile(
    r"(?<![A-Za-z])(?:\d(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?\s*"
    r"(?:M|mM|mol(?:es?)?|mmol|mol/L|g/mol|mol/kg)(?![A-Za-z])"
)


def _chemistry_shaped(text: str) -> bool:
    """A chemistry question by its symbols, amounts or formulas, solved or not."""
    from app.modules.chemistry.input_text import read_chemistry_text
    from app.modules.chemistry.request import is_chemistry_question, names_compound

    if not is_chemistry_question(text):
        return False
    read = read_chemistry_text(text)
    if _CHEMISTRY_SYMBOL.search(read) or _CHEMISTRY_AMOUNT.search(read):
        return True
    if names_compound(read):
        return True
    return _chemical_equation(read)


def _chemical_equation(text: str) -> bool:
    """A reaction of real species ("2H2 + O2 -> 2H2O"), never a mapping such as "A -> B"."""
    from app.modules.chemistry.request import EQUATION_RE
    from app.modules.chemistry.species import parse_reaction

    return any(parse_reaction(match.group(1)) is not None for match in EQUATION_RE.finditer(text))


def _math_curve_request(text: str) -> bool:
    from app.modules.math.tools.school.curve_points import extract_curve_point_intent

    return extract_curve_point_intent(text) is not None


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
    from app.modules.chat import has_code_syntax

    # Pasted code is not a problem to solve: `for (int i = 1; i <= 3; i++)` is a
    # loop, and `n * 2` inside `nums.map` is not algebra.
    if has_code_syntax(text):
        return None
    from app.services.subject_scan import scanner_camera_subject

    # A subject's camera caption says "solve", which the math work-request
    # parser would claim. It is a photo plus a caption, not a math problem.
    scanned = scanner_camera_subject(text)
    if scanned == "chemistry":
        return "chemistry" if chemistry_enabled else None
    if scanned == "physics":
        return "physics"
    # A closed chemistry calculation is chemistry's before physics claims its numbers:
    # "the mass percent of 5 g of sugar in 95 g of water" has masses physics would read.
    # The laws both subjects use (gases, Q = mcΔT, half-lives) are physics' alone, so
    # chemistry never closes on one.
    if chemistry_enabled and _closed_chemistry(text):
        return "chemistry"
    if needs_physics(text):
        if _math_curve_request(text):
            # "h = 20t - 5t^2, find the maximum height" cues physics, but it states the
            # function and asks its maximum: physics extracts nothing, calculus does.

            if extract_physics_intent(text) is None:
                return "math"
        return "physics"
    from app.modules.physics import is_symbol_givens_request

    # Symbol givens with units ("P = 200 W, t = 10 s, find W") are physics even
    # when no catalog law binds; algebra would read W and s as unknowns.
    if is_symbol_givens_request(text):
        return "physics"
    # A pH, Ka or molarity question chemistry could not close is still not algebra: maths
    # would read the x of "1.8 x 10^-5" as its unknown and verify nonsense.
    if chemistry_enabled and _chemistry_shaped(text):
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
    from app.modules.chat import attach_chemistry_fence_hint
    from app.modules.chemistry.context import build_chemistry_augmentation
    from app.modules.chemistry.reading import chemistry_text_for_solve

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
