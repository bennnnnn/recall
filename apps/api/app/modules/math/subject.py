"""Maths as the subject registry asks it (``services/subject_registry``).

The adapter calls what maths already has: the verified block through ``tools.prompt`` and
the direct reply through ``tools.direct``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.modules.math.tools.prompt import NOTHING_TO_GRAPH, build_math_augmentation
from app.services.solving import SubjectAugmentation, VerifiedMathBlock

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.solving import VerifiedSolveBlock
    from app.services.subject_registry import SubjectRequest


@dataclass(frozen=True)
class MathSubject:
    name: Literal["math"] = "math"

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation:
        block, math_verified = await build_math_augmentation(
            request.math_text,
            settings,
            has_image_attachment=request.has_image_attachment,
            image_math_extract=request.image_math_extract,
            needs_math=True,
            prior_user_messages=request.prior_user_messages,
            response_intent_text=request.response_intent_text,
        )
        return SubjectAugmentation(
            subject="math",
            prompt_block=block,
            verified=math_verified,
            # Asking which function to graph is not an unverified answer.
            unverified=(
                block is not None and math_verified is None and block is not NOTHING_TO_GRAPH
            ),
        )

    def direct_reply(
        self,
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


MATH_SUBJECT = MathSubject()
