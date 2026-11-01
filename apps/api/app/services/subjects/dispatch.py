"""The subject dispatcher: a line's subject, its solve and its direct reply.

A line's subject comes from the subject order (``services/subjects/order``), so a subject
package never decides which peer owns a turn. The solve and the direct reply are the
subject's own, asked through its adapter (``services/subjects/registry``); nothing here
reaches into a subject.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.readings import read_off_loop, reading
from app.services.solving import SubjectAugmentation, VerifiedSolveBlock
from app.services.subjects.order import read_subject_reason
from app.services.subjects.registry import SubjectName as SubjectName
from app.services.subjects.registry import SubjectRequest, subject_adapter

if TYPE_CHECKING:
    from app.modules.math.schemas import MathImageExtract


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


# "Dilute …, and also solve …" is two problems. One failed reading of the
# whole line used to stamp "couldn't verify" under two correct answers.
_AND_ALSO = re.compile(r"(?:,\s*|\s+)\band\s+also\b\s+", re.IGNORECASE)


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
    if subject is None:
        return SubjectAugmentation(None, None, None)
    request = SubjectRequest(
        text=user_content,
        math_text=math_text,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
        prior_user_messages=prior_user_messages,
        response_intent_text=response_intent_text,
        redis=redis,
    )
    return await subject_adapter(subject).solve(request, settings)


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
    return subject_adapter(verified.subject).direct_reply(
        verified,
        user_text,
        has_image_attachment=has_image_attachment,
        verified_request_text=verified_request_text,
    )
